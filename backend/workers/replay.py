"""Replays the WUSTL-EHMS-2020 capture through the live detection pipeline.

The README describes an appliance that sniffs traffic off the wire; there is no
capture hardware here, so this stands in for it: it walks the dataset in its
original capture order and pushes each row through exactly the same code path a
sniffed flow would take — vitals_service.ingest_reading() for the patient
monitor stream, then detection_service.submit_detection() for the network flow.
Nothing about the models or the decision table is special-cased for replay.

Feature vectors are built with ml/preprocessing.py's own functions rather than a
copy of them, so a change to the preprocessing rules can't silently drift from
what the models were trained on. Values are handed over UNSCALED —
inference_service applies scaler_v1.pkl itself, the same as for a real flow.

Run from backend/:
    ./venv/Scripts/python.exe -m workers.replay --limit 200 --speed 5
    ./venv/Scripts/python.exe -m workers.replay --start 8000 --limit 50 --speed 2
    ./venv/Scripts/python.exe -m workers.replay --limit 100 --dry-run
"""

import argparse
import sys
import time
from datetime import datetime, timedelta
from pathlib import Path

import numpy as np
import pandas as pd

_BACKEND_DIR = Path(__file__).resolve().parents[1]
_PROJECT_ROOT = _BACKEND_DIR.parent
for _p in (str(_BACKEND_DIR), str(_PROJECT_ROOT / "ml")):
    if _p not in sys.path:
        sys.path.insert(0, _p)

import preprocessing  # noqa: E402  (ml/preprocessing.py, via the sys.path lines above)

from database import SessionLocal  # noqa: E402
from models.device import Device  # noqa: E402
from services import detection_service, inference_service, vitals_service  # noqa: E402

RAW_PATH = _PROJECT_ROOT / "data" / "raw" / "wustl-ehms-2020.csv"

# The capture is one monitor talking to one server, so every row carries the
# same address pair. Which hospital device a row belongs to is ours to decide.
SRC_IP = "10.0.1.172"
DST_IP = "10.0.1.150"

# Stage 4 needs 31 consecutive readings from one device before it can score
# anything, so devices are swapped in blocks rather than per row — round-robin
# would leave every device permanently one reading short of a window.
DEVICE_BLOCK_ROWS = 400


def build_feature_frame(df: pd.DataFrame) -> pd.DataFrame:
    """Raw rows -> the unscaled feature matrix the models expect.

    Mirrors ml/preprocessing.py steps 2-7. Duplicate removal (step 5) is
    deliberately skipped: two identical flows arriving on the wire are two real
    events, and dropping one would desynchronise the row order the vitals
    stream depends on.

    Must be handed the WHOLE capture, never a slice. impute() and winsorize()
    derive medians and 1st/99th percentiles from whatever frame they are given,
    so running them over a 50-row window would clip against that window's own
    spread and produce values the scaler and models never saw in training.
    """
    df = preprocessing.drop_identifiers(df)
    df = preprocessing.coerce_numeric_columns(df)
    df = preprocessing.handle_infinities(df)
    df = preprocessing.impute(df)
    df = preprocessing.winsorize(df, exclude=[preprocessing.LABEL_COLUMN])
    df, _ = preprocessing.encode(df)

    features = inference_service.get_expected_features("v1")
    # A dummy column absent from this slice of the capture means that flag
    # combination never occurred here — zero, not missing.
    frame = df.reindex(columns=features, fill_value=0)
    return frame.astype(float)


_frames_cache: tuple | None = None


def load_frames() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """(raw, features, vitals) for the whole capture, built once per process.

    Parsing the CSV and running preprocessing takes a couple of seconds, which
    is fine for a CLI run but not for an API call that starts a simulation, so
    the result is held for the life of the process. The capture is a fixed file
    on disk — there is nothing to invalidate.
    """
    global _frames_cache
    if _frames_cache is None:
        raw = pd.read_csv(RAW_PATH)
        _frames_cache = (raw, build_feature_frame(raw.copy()), build_vitals_frame(raw))
    return _frames_cache


def build_vitals_frame(raw: pd.DataFrame) -> pd.DataFrame:
    """Vitals in the model's own column order, with sensor dropouts filled.

    Same treatment as ml/train_vitals_lstm.py: a 0 is a dropped reading, not a
    patient whose heart has stopped, so it is carried forward.
    """
    vitals = inference_service.get_vitals_order()
    out = raw[vitals].copy()
    for v in vitals:
        out[v] = out[v].replace(0, np.nan).ffill().bfill()
    return out


def _pick_devices(db, device_uid):
    if device_uid:
        device = db.query(Device).filter(Device.device_uid == device_uid).first()
        if device is None:
            raise SystemExit(f"no device with device_uid '{device_uid}'")
        return [device]
    devices = (
        db.query(Device)
        .filter(Device.device_type.has(is_life_critical=True), Device.status != "quarantined")
        .order_by(Device.id)
        .all()
    )
    if not devices:
        raise SystemExit("no life-critical devices registered — run seed.py and add devices first")
    return devices


def replay(*, start: int, limit: int, speed: float, device_uid: str | None,
           label_filter: int | None, dry_run: bool) -> None:
    # Both frames are built over the full capture first — see build_feature_frame
    # on why the statistics must come from the whole thing — and only then sliced.
    print(f"Loading {RAW_PATH.name} and building feature vectors...")
    raw, all_features, all_vitals = load_frames()

    selected = raw.index
    if label_filter is not None:
        selected = raw.index[raw["Label"] == label_filter]
        print(f"filtered to Label=={label_filter}: {len(selected)} rows")

    chosen = selected[start:start + limit]
    if len(chosen) == 0:
        raise SystemExit(f"no rows at --start {start} ({len(selected)} rows available)")

    window = raw.loc[chosen].reset_index(drop=True)
    features = all_features.loc[chosen].reset_index(drop=True)
    vitals = all_vitals.loc[chosen].reset_index(drop=True)
    vital_names = inference_service.get_vitals_order()

    db = SessionLocal()
    try:
        devices = _pick_devices(db, device_uid)
        pace = "max speed" if speed <= 0 else f"{speed} rows/s"
        note = " — DRY RUN, nothing is written" if dry_run else ""
        print(f"Replaying {len(window)} rows across {len(devices)} device(s) "
              f"({', '.join(d.device_uid for d in devices)}) at {pace}{note}\n")

        interval = 1.0 / speed if speed > 0 else 0.0
        counts: dict[str, int] = {}
        alerts_raised = 0
        # Vitals are timestamped on a synthetic clock so a fast replay still
        # produces a strictly increasing series; get_stage4_status only accepts
        # a reading from the last few minutes, and real-time stamps at 50 rows/s
        # would all collapse into the same instant.
        clock = datetime.utcnow() - timedelta(seconds=len(window))

        for i in range(len(window)):
            row = window.iloc[i]
            device = devices[(start + i) // DEVICE_BLOCK_ROWS % len(devices)]
            truth = "attack" if int(row["Label"]) == 1 else "benign"
            started = time.monotonic()

            if dry_run:
                print(f"[{i + 1:>4}/{len(window)}] {device.device_uid:<16} truth={truth:<6} (dry run)")
            else:
                v = vitals.iloc[i]
                reading = vitals_service.ingest_reading(db, data={
                    "device_id": device.id,
                    "recorded_at": clock + timedelta(seconds=i),
                    "heart_rate": int(v["Heart_rate"]),
                    "spo2": int(v["SpO2"]),
                    "systolic_bp": int(v["SYS"]),
                    "diastolic_bp": int(v["DIA"]),
                    "body_temp": round(float(v["Temp"]), 2),
                    "respiration_rate": int(v["Resp_Rate"]),
                    "raw_payload": {n: float(v[n]) for n in vital_names},
                })

                result = detection_service.submit_detection(
                    db,
                    flow_uid=None,
                    device_id=device.id,
                    feature_vector=features.iloc[i].tolist(),
                    feature_set_version="v1",
                    src_ip=SRC_IP,
                    dst_ip=DST_IP,
                    protocol="TCP",
                    capture_source="dataset",
                )
                detection = result["detection"]
                counts[detection.final_verdict] = counts.get(detection.final_verdict, 0) + 1
                if result["alert"] is not None:
                    alerts_raised += 1

                if detection.stage4_injection_suspected:
                    stage4 = "s4!"
                elif reading.residual_zscore is not None:
                    stage4 = "s4 "
                else:
                    stage4 = "   "
                print(f"[{i + 1:>4}/{len(window)}] {device.device_uid:<16} truth={truth:<6} "
                      f"p={float(detection.stage1_probability):.3f} {stage4} "
                      f"-> {detection.final_verdict:<17} {detection.severity:<8}"
                      f"{' ALERT' if result['alert'] is not None else ''}")

            elapsed = time.monotonic() - started
            if interval > elapsed:
                time.sleep(interval - elapsed)

        if not dry_run:
            print("\nverdicts: " + ", ".join(f"{k}={v}" for k, v in sorted(counts.items())))
            print(f"alerts raised: {alerts_raised}")
    finally:
        db.close()


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--start", type=int, default=0, help="row offset into the capture")
    parser.add_argument("--limit", type=int, default=100, help="how many rows to replay")
    parser.add_argument("--speed", type=float, default=5.0,
                        help="rows per second (0 = as fast as possible)")
    parser.add_argument("--device", dest="device_uid", default=None,
                        help="send everything to one device_uid instead of cycling life-critical devices")
    group = parser.add_mutually_exclusive_group()
    group.add_argument("--attacks-only", action="store_const", const=1, dest="label_filter",
                       help="replay only the labelled attack rows")
    group.add_argument("--benign-only", action="store_const", const=0, dest="label_filter",
                       help="replay only the labelled benign rows")
    parser.add_argument("--dry-run", action="store_true", help="walk the rows without writing anything")
    parser.set_defaults(label_filter=None)
    args = parser.parse_args()

    replay(start=args.start, limit=args.limit, speed=args.speed, device_uid=args.device_uid,
           label_filter=args.label_filter, dry_run=args.dry_run)


if __name__ == "__main__":
    main()
