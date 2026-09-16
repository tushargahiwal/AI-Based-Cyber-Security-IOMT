"""Stage 1 binary detector — M1 Random Forest, exact config from
docs/IoMT_Attack_Detection_Build_Document.pdf §8.2. Also trains the §9.1
baselines (Logistic Regression, Decision Tree, SVM) for the comparison table.

Run: cd ml && ../backend/venv/Scripts/python.exe train_binary.py
"""

import json
import time

import joblib
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

PROCESSED_DIR = "../data/processed"
MODELS_DIR = "../models"


def load_split(name):
    X = pd.read_csv(f"{PROCESSED_DIR}/X_{name}.csv")
    y = pd.read_csv(f"{PROCESSED_DIR}/y_{name}.csv").iloc[:, 0]
    return X, y


def evaluate(model, X, y, *, timed=False):
    if timed:
        start = time.perf_counter()
        y_pred = model.predict(X)
        elapsed_ms = (time.perf_counter() - start) * 1000 / len(X)
    else:
        y_pred = model.predict(X)
        elapsed_ms = None

    y_proba = model.predict_proba(X)[:, 1] if hasattr(model, "predict_proba") else y_pred

    return {
        "accuracy": accuracy_score(y, y_pred),
        "precision": precision_score(y, y_pred, zero_division=0),
        "recall": recall_score(y, y_pred, zero_division=0),
        "f1": f1_score(y, y_pred, zero_division=0),
        "roc_auc": roc_auc_score(y, y_proba),
        "confusion_matrix": confusion_matrix(y, y_pred).tolist(),
        "inference_ms_per_flow": elapsed_ms,
    }


def main():
    print("Loading processed splits...")
    X_train, y_train = load_split("train")
    X_val, y_val = load_split("val")
    X_test, y_test = load_split("test")
    print(f"  train={len(X_train)} (SMOTE-balanced) val={len(X_val)} test={len(X_test)}")

    models = {
        "logistic_regression": LogisticRegression(C=1.0, max_iter=1000, solver="lbfgs"),
        "decision_tree": DecisionTreeClassifier(random_state=42),
        "svm_rbf": SVC(C=10, gamma="scale", probability=True, random_state=42),
        "random_forest_M1": RandomForestClassifier(
            n_estimators=200,
            max_depth=25,
            min_samples_split=5,
            min_samples_leaf=2,
            max_features="sqrt",
            class_weight="balanced_subsample",
            n_jobs=-1,
            random_state=42,
        ),
    }

    results = {}
    for name, model in models.items():
        print(f"\nTraining {name}...")
        t0 = time.perf_counter()
        model.fit(X_train, y_train)
        train_seconds = time.perf_counter() - t0

        val_metrics = evaluate(model, X_val, y_val)
        test_metrics = evaluate(model, X_test, y_test, timed=True)

        results[name] = {"train_seconds": train_seconds, "validation": val_metrics, "test": test_metrics}
        print(
            f"  val:  acc={val_metrics['accuracy']:.4f} f1={val_metrics['f1']:.4f} "
            f"roc_auc={val_metrics['roc_auc']:.4f}"
        )
        print(
            f"  test: acc={test_metrics['accuracy']:.4f} f1={test_metrics['f1']:.4f} "
            f"roc_auc={test_metrics['roc_auc']:.4f} "
            f"latency={test_metrics['inference_ms_per_flow']:.4f} ms/flow"
        )

    print("\nSaving M1 (Random Forest) artifact...")
    # compress=6 takes a 200-tree forest from 32 MB to 9.5 MB with bit-identical
    # predictions and no measurable load-time cost. Size matters here: anything
    # over 10 MB needs Git LFS on Hugging Face, and a smaller artifact means a
    # faster container build every time the Space redeploys.
    joblib.dump(models["random_forest_M1"], f"{MODELS_DIR}/binary_rf_v1.pkl", compress=6)

    with open(f"{MODELS_DIR}/binary_results.json", "w") as f:
        json.dump(results, f, indent=2, default=str)

    print("\n" + "=" * 70)
    print("RESULTS TABLE (binary, WUSTL-EHMS-2020 test split)")
    print("=" * 70)
    print(f"{'Model':<22}{'Accuracy':>10}{'Precision':>11}{'Recall':>9}{'F1':>8}{'ROC-AUC':>9}")
    for name, r in results.items():
        t = r["test"]
        print(
            f"{name:<22}{t['accuracy']:>10.4f}{t['precision']:>11.4f}"
            f"{t['recall']:>9.4f}{t['f1']:>8.4f}{t['roc_auc']:>9.4f}"
        )
    print("=" * 70)
    print("Saved: models/binary_rf_v1.pkl, models/binary_results.json")


if __name__ == "__main__":
    main()
