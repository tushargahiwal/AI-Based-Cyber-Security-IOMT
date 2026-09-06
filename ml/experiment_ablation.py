"""§9.5 ablation — do the engineered features earn their place?

Trains the same two models on the raw flow features alone and then on raw +
engineered, on identical splits with identical seeds, so the only thing that
differs between the two rows of the results table is the feature set.

The engineered baseline (device_profile_deviation) is fitted on the BENIGN
TRAINING ROWS ONLY and then applied to val and test. Fitting it on everything
would leak test-set structure into a training-time feature and inflate the
result — which is the specific mistake this experiment exists to avoid.

Run: cd ml && ../backend/venv/Scripts/python.exe experiment_ablation.py
"""

import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import RandomForestClassifier
from sklearn.metrics import (
    accuracy_score,
    confusion_matrix,
    f1_score,
    precision_score,
    recall_score,
    roc_auc_score,
)
from sklearn.preprocessing import StandardScaler
from xgboost import XGBClassifier

import engineered_features as ef
import preprocessing

RAW_PATH = "../data/raw/wustl-ehms-2020.csv"
PROCESSED_DIR = "../data/processed"
MODELS_DIR = "../models"


def prepared_frame() -> tuple[pd.DataFrame, pd.Series, pd.DataFrame]:
    """(model-ready flow features, label, original raw rows) sharing one index."""
    raw = pd.read_csv(RAW_PATH)
    df = preprocessing.drop_identifiers(raw.copy())
    df = preprocessing.coerce_numeric_columns(df)
    df = preprocessing.handle_infinities(df)
    df = preprocessing.impute(df)
    df = preprocessing.winsorize(df, exclude=[preprocessing.LABEL_COLUMN])
    df, _ = preprocessing.encode(df)

    with open(f"{MODELS_DIR}/feature_order.json") as f:
        columns = json.load(f)["features"]
    X = df.reindex(columns=columns, fill_value=0).astype(float)
    y = raw[preprocessing.LABEL_COLUMN].astype(int)
    return X, y, raw


def evaluate(model, X, y) -> dict:
    y_pred = model.predict(X)
    y_proba = model.predict_proba(X)[:, 1]
    tn, fp, fn, tp = confusion_matrix(y, y_pred).ravel()
    return {
        "accuracy": float(accuracy_score(y, y_pred)),
        "precision": float(precision_score(y, y_pred, zero_division=0)),
        "recall": float(recall_score(y, y_pred, zero_division=0)),
        "f1": float(f1_score(y, y_pred, zero_division=0)),
        "roc_auc": float(roc_auc_score(y, y_proba)),
        "false_positive_rate": float(fp / (fp + tn)) if (fp + tn) else 0.0,
        "confusion_matrix": [[int(tn), int(fp)], [int(fn), int(tp)]],
    }


def models():
    return {
        "random_forest": RandomForestClassifier(
            n_estimators=200, max_depth=25, min_samples_split=5, min_samples_leaf=2,
            max_features="sqrt", class_weight="balanced_subsample", n_jobs=-1, random_state=42,
        ),
        "xgboost": XGBClassifier(
            n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
            colsample_bytree=0.8, eval_metric="logloss", random_state=42, n_jobs=-1,
        ),
    }


def main():
    print(ef.describe())

    print("\nRebuilding the feature matrix from the raw capture...")
    X_flow, y, raw = prepared_frame()
    print(f"  {len(X_flow)} rows, {X_flow.shape[1]} raw flow features")

    # The saved split indices are reused so this experiment sits on exactly the
    # same train/val/test rows as every other result in the report.
    idx = np.load(f"{PROCESSED_DIR}/split_indices.npz")
    train_idx, val_idx, test_idx = idx["train_idx"], idx["val_idx"], idx["test_idx"]
    print(f"  reusing saved splits: train={len(train_idx)} val={len(val_idx)} test={len(test_idx)}")

    print("\nComputing engineered features (baseline fitted on benign TRAIN rows only)...")
    benign_train_mask = pd.Series(False, index=raw.index)
    benign_train_mask.loc[[i for i in train_idx if y.loc[i] == 0]] = True
    X_eng = ef.build(raw, X_flow, benign_mask=benign_train_mask)
    for name in ef.AVAILABLE:
        col = X_eng[name]
        print(f"  {name:<26} mean={col.mean():>10.4f} std={col.std():>10.4f} "
              f"{'(constant — will be dropped)' if col.std() == 0 else ''}")

    # A constant column carries no information and would only add noise to the
    # feature importances.
    useful = [c for c in X_eng.columns if X_eng[c].std() > 0]
    constant = [c for c in X_eng.columns if c not in useful]
    if constant:
        print(f"  dropped as constant on this capture: {', '.join(constant)}")
    X_eng = X_eng[useful]

    print("\nLeakage check — how much of the label can each feature carry alone?")
    agreement = ef.leakage_report(X_eng, y)
    for name, score in sorted(agreement.items(), key=lambda kv: -kv[1]):
        verdict = "LEAK — dropped" if score >= ef.LEAKAGE_AGREEMENT_LIMIT else "ok"
        print(f"  {name:<26} agreement={score:.4f}  {verdict}")
    X_eng, leaky = ef.drop_leaky(X_eng, y)
    if leaky:
        print(f"  refusing to train on: {', '.join(leaky)} "
              f"(see engineered_features.arp_binding_violation)")
    dropped = constant + list(leaky)

    variants = {
        "raw_flow_only": X_flow,
        "raw_plus_engineered": pd.concat([X_flow, X_eng], axis=1),
    }

    results = {}
    for variant, X_all in variants.items():
        print(f"\n--- {variant} ({X_all.shape[1]} features) ---")
        # Scaling is fitted on train only, exactly as preprocessing.py does.
        scaler = StandardScaler().fit(X_all.loc[train_idx])
        X_train = scaler.transform(X_all.loc[train_idx])
        X_test = scaler.transform(X_all.loc[test_idx])
        y_train, y_test = y.loc[train_idx], y.loc[test_idx]

        results[variant] = {}
        for name, model in models().items():
            t0 = time.perf_counter()
            model.fit(X_train, y_train)
            seconds = time.perf_counter() - t0
            metrics = evaluate(model, X_test, y_test)
            metrics["train_seconds"] = seconds
            results[variant][name] = metrics
            print(f"  {name:<16} acc={metrics['accuracy']:.4f} recall={metrics['recall']:.4f} "
                  f"f1={metrics['f1']:.4f} roc_auc={metrics['roc_auc']:.4f}")

            if variant == "raw_plus_engineered" and hasattr(model, "feature_importances_"):
                importances = pd.Series(model.feature_importances_, index=X_all.columns)
                engineered_share = importances[X_eng.columns].sum()
                ranked = importances.sort_values(ascending=False)
                rank_of = {c: int(np.where(ranked.index == c)[0][0]) + 1 for c in X_eng.columns}
                results[variant][name]["engineered_importance_share"] = float(engineered_share)
                results[variant][name]["engineered_ranks"] = rank_of
                print(f"    engineered features hold {engineered_share:.1%} of total importance; "
                      f"ranks {rank_of}")

    payload = {
        "engineered_available": ef.AVAILABLE,
        "engineered_unavailable": ef.UNAVAILABLE,
        "engineered_used": list(X_eng.columns),
        "engineered_dropped_constant": dropped,
        "results": results,
    }
    with open(f"{MODELS_DIR}/ablation_results.json", "w") as f:
        json.dump(payload, f, indent=2)

    print("\n" + "=" * 82)
    print("§9.5 ABLATION — effect of the engineered features (WUSTL test split)")
    print("=" * 82)
    print(f"{'Model':<14}{'Feature set':<24}{'Accuracy':>10}{'Recall':>9}{'F1':>8}{'ROC-AUC':>10}")
    for name in models():
        for variant in variants:
            r = results[variant][name]
            print(f"{name:<14}{variant:<24}{r['accuracy']:>10.4f}{r['recall']:>9.4f}"
                  f"{r['f1']:>8.4f}{r['roc_auc']:>10.4f}")
        a, b = results["raw_flow_only"][name], results["raw_plus_engineered"][name]
        print(f"{'':<14}{'delta':<24}{b['accuracy'] - a['accuracy']:>+10.4f}"
              f"{b['recall'] - a['recall']:>+9.4f}{b['f1'] - a['f1']:>+8.4f}"
              f"{b['roc_auc'] - a['roc_auc']:>+10.4f}")
    print("=" * 82)
    print("Saved: models/ablation_results.json")


if __name__ == "__main__":
    main()
