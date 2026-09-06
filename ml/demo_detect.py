"""End-to-end proof: real dataset rows -> live /api/v1/detect -> DB rows.

Reuses the exact cleaning steps from preprocessing.py (through encoding, but
NOT scaling/SMOTE — the API applies the saved scaler itself, matching the
doc's "the API must apply the exact same transform" design).

Run: cd ml && ../backend/venv/Scripts/python.exe demo_detect.py
"""

import json
import sys
import uuid
import warnings
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "backend"))
warnings.filterwarnings("ignore")

import pandas as pd  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402

import preprocessing as prep  # noqa: E402
from database import SessionLocal, engine  # noqa: E402
from main import app  # noqa: E402
from models.role import Role  # noqa: E402
from models.user import User  # noqa: E402
from services.security import hash_password  # noqa: E402
from services.user_service import delete_user  # noqa: E402


def build_raw_features() -> pd.DataFrame:
    df = prep.load_raw()
    df = prep.drop_identifiers(df)
    df = prep.coerce_numeric_columns(df)
    df = prep.handle_infinities(df)
    df = prep.impute(df)
    df = prep.drop_duplicates(df)
    df = prep.winsorize(df, exclude=[prep.LABEL_COLUMN])
    df, _ = prep.encode(df)
    return df


def main():
    with open("../models/feature_order.json") as f:
        feature_order = json.load(f)["features"]

    print("Rebuilding raw (unscaled) features via the same preprocessing steps...")
    df = build_raw_features()

    client = TestClient(app)

    demo_username = f"demo_detect_{uuid.uuid4().hex[:8]}"

    db = SessionLocal()
    admin_role = db.query(Role).filter(Role.name == "admin").first()
    tmp = User(
        role_id=admin_role.id, username=demo_username, email=f"{demo_username}@example.com",
        password_hash=hash_password("DemoPass123"),
    )
    db.add(tmp)
    db.commit()
    db.close()

    r = client.post("/api/v1/auth/login", json={"username": demo_username, "password": "DemoPass123"})
    headers = {"Authorization": f"Bearer {r.json()['access_token']}"}

    benign_rows = df[df["Label"] == 0].sample(3, random_state=7)
    alteration_rows = df[df["Attack Category"] == "Data Alteration"].sample(3, random_state=7)
    spoofing_rows = df[df["Attack Category"] == "Spoofing"].sample(3, random_state=7)
    sample = pd.concat([benign_rows, alteration_rows, spoofing_rows])

    print(f"\nSubmitting {len(sample)} real rows through the live /api/v1/detect endpoint...\n")
    correct = 0
    for idx, row in sample.iterrows():
        true_label = int(row["Label"])
        true_family = row["Attack Category"]
        feature_vector = [float(row[c]) for c in feature_order]

        resp = client.post(
            "/api/v1/detect",
            json={
                "device_id": None,
                "feature_vector": feature_vector,
                "feature_set_version": "v1",
                "protocol": "OTHER",
                "capture_source": "dataset",
            },
            headers=headers,
        )
        body = resp.json()
        predicted_label = 1 if body["stage1"]["label"] == "malicious" else 0
        hit = predicted_label == true_label
        correct += hit
        mark = "correct" if hit else "WRONG"
        stage2_str = (
            f"stage2={body['stage2']['attack_family']} (p={body['stage2']['confidence']:.4f})"
            if body.get("stage2")
            else "stage2=-"
        )
        stage3_str = (
            f"stage3_anomaly={body['stage3']['is_anomaly']} (score={body['stage3']['anomaly_score']:.3f})"
            if body.get("stage3")
            else "stage3=-"
        )
        print(
            f"row {idx:>6}  true_family={true_family:<16} stage1={body['stage1']['label']:<9} "
            f"(p={body['stage1']['probability']:.4f})  {stage2_str:<38} {stage3_str:<34} "
            f"verdict={body['final_verdict']:<16} severity={body['severity']:<8} [{mark}]"
        )

    print(f"\n{correct}/{len(sample)} correct on this sample")

    print("\nSweeping 40 random benign rows looking for any Stage 3 flags (honest search, not cherry-picked)...")
    sweep = df[df["Label"] == 0].sample(40, random_state=99)
    zero_day_hits = 0
    for idx, row in sweep.iterrows():
        feature_vector = [float(row[c]) for c in feature_order]
        resp = client.post(
            "/api/v1/detect",
            json={
                "device_id": None,
                "feature_vector": feature_vector,
                "feature_set_version": "v1",
                "protocol": "OTHER",
                "capture_source": "dataset",
            },
            headers=headers,
        )
        body = resp.json()
        if body["final_verdict"] == "zero_day_suspect":
            zero_day_hits += 1
            print(
                f"  row {idx:>6}: stage1={body['stage1']['label']} (p={body['stage1']['probability']:.4f}) "
                f"stage3_anomaly_score={body['stage3']['anomaly_score']:.3f} -> zero_day_suspect"
            )
    print(f"  {zero_day_hits}/{len(sweep)} benign rows flagged zero_day_suspect by Stage 3 "
          f"(expected roughly ~2.5% given the 97.5th-percentile threshold)")

    print("\nCleaning up demo account (soft-delete — keeps the detections/flows as real records)...")
    db = SessionLocal()
    tmp_user = db.query(User).filter(User.username == demo_username).first()
    delete_user(db, target_user_id=tmp_user.id, actor_user_id=-1)
    db.close()

    with engine.connect() as conn:
        from sqlalchemy import text

        n_flows = conn.execute(text("SELECT COUNT(*) FROM network_flows")).scalar()
        n_detections = conn.execute(text("SELECT COUNT(*) FROM detections")).scalar()
        print(f"\nnetwork_flows rows in DB: {n_flows}")
        print(f"detections rows in DB:    {n_detections}")


if __name__ == "__main__":
    main()
