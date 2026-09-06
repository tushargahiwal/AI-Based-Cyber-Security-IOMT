"""Stage 2 multi-class attack-family classifier — M2 XGBoost, adapted from
docs/IoMT_Attack_Detection_Build_Document.pdf §8.3 (num_class changed from 6
to 3: WUSTL-EHMS-2020 only carries Spoofing and Data Alteration attacks, not
the full CICIoMT2024 taxonomy — reporting a real 3-class number, not a fake 6).

Reuses preprocessing.py's cleaning steps and the SAME fitted scaler_v1.pkl as
Stage 1 (transform only, not re-fit) — Stage 1 and Stage 2 must agree on what
a given feature vector "means", per the doc's single-transform rule (§7.4).

Run: cd ml && ../backend/venv/Scripts/python.exe train_multiclass.py
"""

import json

import joblib
import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.model_selection import train_test_split
from xgboost import XGBClassifier

import preprocessing as prep

SCALER_PATH = "../data/scalers/scaler_v1.pkl"
ENCODER_PATH = "../data/scalers/attack_family_encoder_v1.pkl"
MODELS_DIR = "../models"


def build_clean_dataframe() -> pd.DataFrame:
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
    with open(f"{MODELS_DIR}/feature_order.json") as f:
        feature_cols = json.load(f)["features"]

    print("Rebuilding cleaned (unscaled) dataframe...")
    df = build_clean_dataframe()
    X = df[feature_cols]
    y = df["attack_family_encoded"]

    encoder = joblib.load(ENCODER_PATH)
    class_names = list(encoder.classes_)
    print(f"Classes: {class_names} (encoded 0..{len(class_names)-1})")

    print("Stratified 70/15/15 split (independent of the binary split)...")
    X_train, X_temp, y_train, y_temp = train_test_split(X, y, test_size=0.30, stratify=y, random_state=42)
    X_val, X_test, y_val, y_test = train_test_split(X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=42)
    print(f"  train={len(X_train)} val={len(X_val)} test={len(X_test)}")

    print("Transforming with Stage 1's already-fitted scaler (no re-fit)...")
    scaler = joblib.load(SCALER_PATH)
    X_train_s = scaler.transform(X_train)
    X_val_s = scaler.transform(X_val)
    X_test_s = scaler.transform(X_test)

    print("SMOTE on training split only (multiclass)...")
    print(f"  before: {y_train.value_counts().to_dict()}")
    X_train_res, y_train_res = SMOTE(random_state=42).fit_resample(X_train_s, y_train)
    print(f"  after:  {pd.Series(y_train_res).value_counts().to_dict()}")

    models = {
        "logistic_regression": LogisticRegression(max_iter=2000),
        "xgboost_M2": XGBClassifier(
            objective="multi:softprob",
            num_class=len(class_names),
            n_estimators=400,
            max_depth=8,
            learning_rate=0.08,
            subsample=0.85,
            colsample_bytree=0.85,
            reg_lambda=1.5,
            reg_alpha=0.5,
            tree_method="hist",
            eval_metric="mlogloss",
            random_state=42,
        ),
    }

    results = {}
    for name, model in models.items():
        print(f"\nTraining {name}...")
        model.fit(X_train_res, y_train_res)
        y_pred = model.predict(X_test_s)

        report = classification_report(y_test, y_pred, target_names=class_names, output_dict=True, zero_division=0)
        cm = confusion_matrix(y_test, y_pred).tolist()
        macro_f1 = f1_score(y_test, y_pred, average="macro")

        results[name] = {"per_class": report, "confusion_matrix": cm, "macro_f1": macro_f1}
        print(f"  macro-F1: {macro_f1:.4f}")
        for cls in class_names:
            r = report[cls]
            print(f"    {cls:<18} precision={r['precision']:.4f} recall={r['recall']:.4f} f1={r['f1-score']:.4f} support={int(r['support'])}")

    print("\nSaving M2 (XGBoost) artifact...")
    joblib.dump(models["xgboost_M2"], f"{MODELS_DIR}/multiclass_xgb_v1.pkl")

    with open(f"{MODELS_DIR}/multiclass_results.json", "w") as f:
        json.dump({"class_names": class_names, "results": results}, f, indent=2, default=str)

    print("\n" + "=" * 70)
    print(f"CONFUSION MATRIX (xgboost_M2, rows=true, cols=predicted, order={class_names})")
    print("=" * 70)
    for row_name, row in zip(class_names, results["xgboost_M2"]["confusion_matrix"]):
        print(f"  {row_name:<18} {row}")
    print("Saved: models/multiclass_xgb_v1.pkl, models/multiclass_results.json")


if __name__ == "__main__":
    main()
