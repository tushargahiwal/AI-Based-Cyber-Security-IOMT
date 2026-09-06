"""M10 — Stacking Ensemble, doc §8.9.

The doc stacks M1/M2/M3. This stacks what actually exists and adds something the
doc does not: the three Stage 3 novelty scores go in as meta-features alongside
the supervised probabilities. That matters because the supervised models and the
novelty models fail on *different* flows — a supervised model is confident and
wrong on an attack it was never trained on, which is exactly when the
benign-only models are suspicious. A meta-learner can learn that pattern; a
fixed decision table cannot.

The one thing that would make these numbers a lie is training the meta-learner
on base-model predictions over the SAME rows the base models were fitted on:
their training predictions are near-perfect and the meta-learner would just
learn to trust them. So the base models are fitted on train, the meta-learner is
fitted on their VALIDATION predictions, and test is touched once at the end.

Run: cd ml && ../backend/venv/Scripts/python.exe train_stacking.py
"""

import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from xgboost import XGBClassifier

PROCESSED_DIR = "../data/processed"
MODELS_DIR = "../models"
SCALER_DIR = "../data/scalers"

META_FEATURES = [
    "rf_probability",
    "xgb_probability",
    "autoencoder_error",
    "isolation_forest_score",
    "one_class_svm_score",
]


def load_split(name):
    X = pd.read_csv(f"{PROCESSED_DIR}/X_{name}.csv")
    y = pd.read_csv(f"{PROCESSED_DIR}/y_{name}.csv").iloc[:, 0]
    return X, y


def evaluate(y_true, y_pred, y_proba) -> dict:
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred).ravel()
    return {
        "accuracy": float(accuracy_score(y_true, y_pred)),
        "precision": float(precision_score(y_true, y_pred, zero_division=0)),
        "recall": float(recall_score(y_true, y_pred, zero_division=0)),
        "f1": float(f1_score(y_true, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y_true, y_proba)),
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }


def build_meta_features(X, *, rf, xgb, autoencoder, iforest, ocsvm) -> np.ndarray:
    """One row per flow: what each base model thinks of it."""
    values = np.array(X, dtype="float32")
    reconstruction = np.asarray(autoencoder(values, training=False))
    return np.column_stack([
        rf.predict_proba(X)[:, 1],
        xgb.predict_proba(X)[:, 1],
        np.mean(np.square(values - reconstruction), axis=1),
        -iforest.score_samples(X),   # negated so higher = more anomalous everywhere
        -ocsvm.score_samples(X),
    ])


def main():
    from tensorflow import keras

    print("Loading processed splits...")
    X_train, y_train = load_split("train")
    X_val, y_val = load_split("val")
    print(f"  train={len(X_train)} val={len(X_val)}")

    print("\nLoading the fitted base models...")
    rf = joblib.load(f"{MODELS_DIR}/binary_rf_v1.pkl")
    autoencoder = keras.models.load_model(f"{MODELS_DIR}/autoencoder_v1.keras")
    iforest = joblib.load(f"{MODELS_DIR}/isolation_forest_v1.pkl")
    ocsvm = joblib.load(f"{MODELS_DIR}/one_class_svm_v1.pkl")
    print("  M1 random forest, M4 autoencoder, M5 isolation forest, M7 one-class SVM")

    print("\nTraining the binary XGBoost base learner (M2 as a Stage 1 alternate)...")
    t0 = time.perf_counter()
    # scale_pos_weight is 1 here: the training split was already balanced by SMOTE
    # in preprocessing, so re-weighting would over-correct.
    xgb = XGBClassifier(
        n_estimators=300,
        max_depth=6,
        learning_rate=0.1,
        subsample=0.8,
        colsample_bytree=0.8,
        eval_metric="logloss",
        random_state=42,
        n_jobs=-1,
    )
    xgb.fit(X_train, y_train)
    xgb_seconds = time.perf_counter() - t0
    print(f"  fitted in {xgb_seconds:.2f}s")

    print("\nBuilding meta-features from VALIDATION predictions...")
    base = dict(rf=rf, xgb=xgb, autoencoder=autoencoder, iforest=iforest, ocsvm=ocsvm)
    meta_val = build_meta_features(X_val, **base)

    print("Training the meta-learner...")
    t0 = time.perf_counter()
    meta = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced")
    meta.fit(meta_val, y_val)
    meta_seconds = time.perf_counter() - t0
    print("  learned weights:")
    for name, weight in zip(META_FEATURES, meta.coef_[0]):
        print(f"    {name:<24}{weight:+.4f}")

    print("\nEvaluating everything on the held-out test split...")
    X_test, y_test = load_split("test")
    meta_test = build_meta_features(X_test, **base)

    results = {}
    rf_proba = meta_test[:, 0]
    xgb_proba = meta_test[:, 1]
    results["random_forest_M1"] = evaluate(y_test, (rf_proba >= 0.5).astype(int), rf_proba)
    results["xgboost_M2"] = evaluate(y_test, (xgb_proba >= 0.5).astype(int), xgb_proba)

    stack_proba = meta.predict_proba(meta_test)[:, 1]
    t0 = time.perf_counter()
    meta.predict_proba(meta_test[:200])
    meta_latency = (time.perf_counter() - t0) * 1000 / 200
    results["stacking_M10"] = evaluate(y_test, (stack_proba >= 0.5).astype(int), stack_proba)
    results["stacking_M10"]["meta_only_inference_ms_per_flow"] = meta_latency

    # Does the unsupervised half actually pay for itself, or is this just RF+XGB?
    print("\nAblation: the same meta-learner on supervised probabilities only...")
    meta_supervised = LogisticRegression(C=1.0, max_iter=1000, class_weight="balanced")
    meta_supervised.fit(meta_val[:, :2], y_val)
    sup_proba = meta_supervised.predict_proba(meta_test[:, :2])[:, 1]
    results["stacking_supervised_only"] = evaluate(
        y_test, (sup_proba >= 0.5).astype(int), sup_proba
    )

    payload = {
        "meta_features": META_FEATURES,
        "meta_learner_weights": dict(zip(META_FEATURES, meta.coef_[0].tolist())),
        "meta_learner_intercept": float(meta.intercept_[0]),
        "protocol": ("base models fitted on train; meta-learner fitted on validation "
                     "predictions; test used once"),
        "xgb_train_seconds": xgb_seconds,
        "meta_train_seconds": meta_seconds,
        "test": results,
    }
    joblib.dump(xgb, f"{MODELS_DIR}/binary_xgb_v1.pkl")
    joblib.dump(meta, f"{MODELS_DIR}/stacking_meta_v1.pkl")
    with open(f"{MODELS_DIR}/stacking_results.json", "w") as f:
        json.dump(payload, f, indent=2)

    print("\n" + "=" * 78)
    print("STACKING COMPARISON — WUSTL-EHMS-2020 test split")
    print("=" * 78)
    print(f"{'Model':<28}{'Accuracy':>10}{'Recall':>9}{'F1':>8}{'ROC-AUC':>10}{'FPR':>9}")
    labels = {
        "random_forest_M1": "M1 Random Forest",
        "xgboost_M2": "M2 XGBoost",
        "stacking_supervised_only": "  stack: supervised only",
        "stacking_M10": "M10 Stacking (+ novelty)",
    }
    for key in ["random_forest_M1", "xgboost_M2", "stacking_supervised_only", "stacking_M10"]:
        r = results[key]
        print(f"{labels[key]:<28}{r['accuracy']:>10.4f}{r['recall']:>9.4f}"
              f"{r['f1']:>8.4f}{r['roc_auc']:>10.4f}{r['false_positive_rate']:>9.4f}")
    print("=" * 78)
    print("Saved: models/binary_xgb_v1.pkl, models/stacking_meta_v1.pkl,")
    print("       models/stacking_results.json")


if __name__ == "__main__":
    main()
