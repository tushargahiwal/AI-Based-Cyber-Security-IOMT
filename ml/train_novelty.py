"""Stage 3 companions — M5 Isolation Forest and M7 One-Class SVM, doc §8.6/§8.8.

The autoencoder (M4) already answers "does this flow look like the benign
traffic I was trained on". These two answer the same question with completely
different inductive biases — random axis-aligned splits for the forest, a kernel
boundary for the SVM — which is exactly why they are worth having: if all three
agree a flow is strange, that is a much stronger zero-day signal than one model
saying so alone.

Trained on BENIGN ROWS ONLY, like M4. Attack rows are never seen during fitting;
they are only used to measure detection rate afterwards. Breaking that is the
single easiest way to fake a good zero-day number, so it is enforced here by
construction: the attack split is not even loaded until after fit().

Run: cd ml && ../backend/venv/Scripts/python.exe train_novelty.py
"""

import json
import time

import joblib
import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest
from sklearn.metrics import confusion_matrix, f1_score, precision_score, recall_score, roc_auc_score
from sklearn.svm import OneClassSVM

PROCESSED_DIR = "../data/processed"
MODELS_DIR = "../models"

# Matches the autoencoder's threshold rule (doc §8.5): the score at which 97.5%
# of benign validation flows sit below, so all three Stage 3 models are
# calibrated to the same benign false-positive budget and can be compared.
BENIGN_PERCENTILE = 97.5


def load_split(name):
    X = pd.read_csv(f"{PROCESSED_DIR}/X_{name}.csv")
    y = pd.read_csv(f"{PROCESSED_DIR}/y_{name}.csv").iloc[:, 0]
    return X, y


def evaluate(scores_benign_val, scores_test, y_test, name):
    """Higher score = more anomalous, for both models (both are negated below)."""
    threshold = float(np.percentile(scores_benign_val, BENIGN_PERCENTILE))
    y_pred = (scores_test > threshold).astype(int)

    tn, fp, fn, tp = confusion_matrix(y_test, y_pred).ravel()
    metrics = {
        "threshold": threshold,
        "threshold_percentile": BENIGN_PERCENTILE,
        "detection_rate": float(recall_score(y_test, y_pred, zero_division=0)),
        "precision": float(precision_score(y_test, y_pred, zero_division=0)),
        "f1": float(f1_score(y_test, y_pred, zero_division=0)),
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        # AUC is threshold-free, so it says how well the score SEPARATES the two
        # classes regardless of where the cut is drawn — the fairer comparison.
        "roc_auc": float(roc_auc_score(y_test, scores_test)),
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }
    print(f"  {name}: detection={metrics['detection_rate']:.4f} "
          f"FPR={metrics['false_positive_rate']:.4f} roc_auc={metrics['roc_auc']:.4f}")
    return metrics


def main():
    print("Loading processed splits...")
    X_train, y_train = load_split("train")
    X_val, y_val = load_split("val")

    benign_train = X_train[y_train == 0]
    benign_val = X_val[y_val == 0]
    print(f"  benign train={len(benign_train)} benign val={len(benign_val)}")
    print("  (attack rows are not loaded until after fitting)")

    results = {}

    print("\nFitting M5 Isolation Forest on benign traffic only...")
    t0 = time.perf_counter()
    iforest = IsolationForest(
        n_estimators=200,
        contamination="auto",
        max_samples="auto",
        n_jobs=-1,
        random_state=42,
    )
    iforest.fit(benign_train)
    iforest_seconds = time.perf_counter() - t0
    print(f"  fitted in {iforest_seconds:.2f}s")

    print("\nFitting M7 One-Class SVM on benign traffic only...")
    t0 = time.perf_counter()
    # nu is the upper bound on the fraction of training points allowed to fall
    # outside the boundary; 0.025 mirrors the 97.5th-percentile budget above.
    ocsvm = OneClassSVM(kernel="rbf", gamma="scale", nu=0.025)
    ocsvm.fit(benign_train)
    ocsvm_seconds = time.perf_counter() - t0
    print(f"  fitted in {ocsvm_seconds:.2f}s")

    # Only now is the labelled test split brought in.
    X_test, y_test = load_split("test")
    print(f"\nEvaluating on the held-out test split ({len(X_test)} flows, "
          f"{int(y_test.sum())} attacks)...")

    # Both estimators return HIGHER = more normal; negate so higher = more anomalous.
    for key, model, seconds in [
        ("isolation_forest_M5", iforest, iforest_seconds),
        ("one_class_svm_M7", ocsvm, ocsvm_seconds),
    ]:
        val_scores = -model.score_samples(benign_val) if hasattr(model, "score_samples") \
            else -model.decision_function(benign_val)
        test_scores = -model.score_samples(X_test) if hasattr(model, "score_samples") \
            else -model.decision_function(X_test)

        t0 = time.perf_counter()
        model.decision_function(X_test[:200])
        latency = (time.perf_counter() - t0) * 1000 / 200

        metrics = evaluate(val_scores, test_scores, y_test, key)
        metrics["inference_ms_per_flow"] = latency
        results[key] = {"train_seconds": seconds, "test": metrics}

    print("\nSaving artifacts...")
    joblib.dump(iforest, f"{MODELS_DIR}/isolation_forest_v1.pkl")
    joblib.dump(ocsvm, f"{MODELS_DIR}/one_class_svm_v1.pkl")
    with open(f"{MODELS_DIR}/novelty_results.json", "w") as f:
        json.dump(results, f, indent=2)

    # Put them next to the autoencoder so the report has one comparison table.
    try:
        with open(f"{MODELS_DIR}/autoencoder_results.json") as f:
            ae = json.load(f)
    except FileNotFoundError:
        ae = None

    print("\n" + "=" * 74)
    print("STAGE 3 NOVELTY DETECTION — benign-only training, WUSTL test split")
    print("=" * 74)
    print(f"{'Model':<26}{'Detection':>11}{'FPR':>9}{'ROC-AUC':>10}{'ms/flow':>10}")
    if ae:
        print(f"{'M4 Deep Autoencoder':<26}{ae['test_detection_rate']:>11.4f}"
              f"{ae['test_false_positive_rate']:>9.4f}{'—':>10}{'—':>10}")
    for key, r in results.items():
        t = r["test"]
        label = {"isolation_forest_M5": "M5 Isolation Forest",
                 "one_class_svm_M7": "M7 One-Class SVM"}[key]
        print(f"{label:<26}{t['detection_rate']:>11.4f}{t['false_positive_rate']:>9.4f}"
              f"{t['roc_auc']:>10.4f}{t['inference_ms_per_flow']:>10.4f}")
    print("=" * 74)
    print("Saved: models/isolation_forest_v1.pkl, models/one_class_svm_v1.pkl,")
    print("       models/novelty_results.json")


if __name__ == "__main__":
    main()
