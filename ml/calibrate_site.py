"""Recalibrates Stage 3 and Stage 4 to one hospital's own traffic.

Why this exists, with evidence rather than theory. Running the shipped models
over a synthetic capture of ordinary MQTT monitor traffic gave:

    9 flows scored, 9 alerts, verdicts: zero_day_suspect=9

Six of those nine flows were deliberately normal. Stage 1 sat at p ~ 0.50 — a
coin flip — and Stage 3 flagged everything, because "normal" to those models
means WUSTL-EHMS-2020: one monitor, one server, a university lab. A hospital ICU
is thirty devices from five vendors with rounds, shift changes and Wi-Fi
congestion. Deployed uncalibrated, this system alerts on everything, and the
staff switch it off inside a week. That is the single most common way an IDS
deployment fails.

What this script does NOT do is retrain the models. It moves their DECISION
THRESHOLDS onto the site's own benign traffic, which is the part that has to be
site-specific:

  * Stage 3 (autoencoder): the reconstruction error below which this site's own
    traffic sits, at a false-positive budget you choose.
  * Stage 4 (vitals LSTM): the per-vital residual spread for this site's own
    patients and monitors.

Input is a baseline captured from the site with `workers/sniffer.py` during a
period the site confirms was quiet. That confirmation is a human judgement and
this script cannot make it — if attacks are in the baseline, they are calibrated
in as normal, and it will be blind to them.

    cd ml
    ../backend/venv/Scripts/python.exe calibrate_site.py --baseline site_baseline.csv \\
        --site "Aarogya Hospital ICU-1" --fp-budget 1.0
"""

import argparse
import json
import sys
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd

_ML_DIR = Path(__file__).resolve().parent
_PROJECT_ROOT = _ML_DIR.parent
sys.path.insert(0, str(_PROJECT_ROOT / "backend"))

MODELS_DIR = _PROJECT_ROOT / "models"
SCALER_DIR = _PROJECT_ROOT / "data" / "scalers"

# Below this many benign flows a percentile is not a measurement, it is an
# accident of which few flows happened to be captured.
MIN_BASELINE_FLOWS = 500
MIN_BASELINE_VITALS = 500


def _percentile_threshold(scores: np.ndarray, fp_budget_percent: float) -> float:
    """The score below which (100 - budget)% of benign traffic sits.

    Setting the threshold from the site's own distribution is the whole point:
    a budget of 1% means one alert per hundred benign flows HERE, whatever the
    raw error values happen to be on this network.
    """
    return float(np.percentile(scores, 100.0 - fp_budget_percent))


def calibrate_stage3(features: pd.DataFrame, fp_budget: float) -> dict:
    from tensorflow import keras

    model = keras.models.load_model(MODELS_DIR / "autoencoder_v1.keras")
    scaler = joblib.load(SCALER_DIR / "scaler_v1.pkl")

    scaled = scaler.transform(features.to_numpy()).astype("float32")
    reconstruction = np.asarray(model(scaled, training=False))
    errors = np.mean(np.square(scaled - reconstruction), axis=1)

    threshold = _percentile_threshold(errors, fp_budget)
    with open(MODELS_DIR / "autoencoder_results.json") as f:
        shipped = json.load(f)["threshold"]

    return {
        "threshold": threshold,
        "shipped_threshold": shipped,
        "ratio_to_shipped": threshold / shipped if shipped else None,
        "flows": int(len(errors)),
        "error_median": float(np.median(errors)),
        "error_p99": float(np.percentile(errors, 99)),
        "expected_false_positive_rate": fp_budget / 100.0,
    }


def calibrate_stage4(vitals: pd.DataFrame, fp_budget: float) -> dict:
    from tensorflow import keras

    with open(MODELS_DIR / "vitals_lstm_results.json") as f:
        meta = json.load(f)
    order, window = meta["vitals_order"], meta["window"]

    model = keras.models.load_model(MODELS_DIR / "vitals_lstm_v1.keras")
    scaler = joblib.load(SCALER_DIR / "vitals_scaler_v1.pkl")

    series = vitals[order].to_numpy(dtype=float)
    scaled = scaler.transform(series)

    # Sliding windows over the site's own readings, in capture order.
    X = np.array([scaled[i:i + window] for i in range(len(scaled) - window)], dtype="float32")
    y = scaled[window:]
    predicted = np.asarray(model(X, training=False))
    residuals = np.abs(y - predicted)

    # Residual spread is per-vital: a 3 bpm error and a 3 degree error are not
    # the same size of surprise.
    residual_std = residuals.std(axis=0)
    residual_std = np.where(residual_std < 1e-6, 1e-6, residual_std)
    z = residuals / residual_std

    threshold = _percentile_threshold(z.max(axis=1), fp_budget)
    return {
        "z_threshold": threshold,
        "shipped_z_threshold": 3.0,
        "residual_std": residual_std.tolist(),
        "shipped_residual_std": meta["residual_std"],
        "vitals_order": order,
        "windows": int(len(X)),
        "expected_false_positive_rate": fp_budget / 100.0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__.split("\n")[0])
    parser.add_argument("--baseline", required=True,
                        help="CSV of benign flows captured at the site (feature_order.json columns)")
    parser.add_argument("--vitals", default=None,
                        help="CSV of benign vitals readings in capture order (optional)")
    parser.add_argument("--site", required=True, help="which deployment this calibration is for")
    parser.add_argument("--fp-budget", type=float, default=1.0,
                        help="alerts per 100 benign flows you are willing to accept (default 1.0)")
    parser.add_argument("--force", action="store_true",
                        help="calibrate even from a baseline too small to be meaningful")
    args = parser.parse_args()

    with open(MODELS_DIR / "feature_order.json") as f:
        columns = json.load(f)["features"]

    print(f"Site: {args.site}")
    print(f"False-positive budget: {args.fp_budget}% of benign flows\n")

    flows = pd.read_csv(args.baseline)
    missing = [c for c in columns if c not in flows.columns]
    if missing:
        raise SystemExit(
            f"baseline is missing {len(missing)} feature columns, e.g. {missing[:4]}. "
            "Capture it with workers/sniffer.py so the columns match what the models expect."
        )
    flows = flows[columns].astype(float)
    print(f"Baseline: {len(flows)} flows")

    if len(flows) < MIN_BASELINE_FLOWS and not args.force:
        raise SystemExit(
            f"only {len(flows)} flows — below {MIN_BASELINE_FLOWS}, a percentile here is noise, "
            "not a threshold. Capture a longer quiet period, or pass --force and treat the "
            "result as provisional."
        )

    print("Calibrating Stage 3 (autoencoder) on this site's benign traffic...")
    stage3 = calibrate_stage3(flows, args.fp_budget)
    print(f"  threshold {stage3['shipped_threshold']:.4f} (shipped) -> "
          f"{stage3['threshold']:.4f} (this site)  ×{stage3['ratio_to_shipped']:.2f}")

    stage4 = None
    if args.vitals:
        readings = pd.read_csv(args.vitals)
        print(f"\nBaseline vitals: {len(readings)} readings")
        if len(readings) < MIN_BASELINE_VITALS and not args.force:
            raise SystemExit(f"only {len(readings)} readings — below {MIN_BASELINE_VITALS}")
        print("Calibrating Stage 4 (vitals LSTM)...")
        stage4 = calibrate_stage4(readings, args.fp_budget)
        print(f"  z-threshold 3.00 (shipped) -> {stage4['z_threshold']:.2f} (this site)")
        for name, shipped, here in zip(stage4["vitals_order"],
                                       stage4["shipped_residual_std"], stage4["residual_std"]):
            print(f"    {name:<12} residual std {shipped:.4f} -> {here:.4f}")

    payload = {
        "site": args.site,
        "calibrated_at": datetime.utcnow().isoformat(),
        "fp_budget_percent": args.fp_budget,
        "baseline_file": args.baseline,
        "stage3": stage3,
        "stage4": stage4,
        "warning": ("Thresholds are only as trustworthy as the baseline. If an attack was live "
                    "during the capture, it has been calibrated in as normal and the system is "
                    "now blind to it."),
    }
    out = MODELS_DIR / "site_calibration.json"
    with open(out, "w") as f:
        json.dump(payload, f, indent=2)

    print(f"\nWritten to {out.relative_to(_PROJECT_ROOT)}")
    print("\nTo put these live, update the ml_models rows for this site:")
    print(f"  Stage 3 threshold -> {stage3['threshold']:.6f}")
    if stage4:
        print(f"  Stage 4 threshold -> {stage4['z_threshold']:.4f}")
    print("\nApply them in shadow mode first — alerts visible to IT only — and measure the real")
    print("false-positive rate for a week before any clinical staff sees an alert from them.")


if __name__ == "__main__":
    main()
