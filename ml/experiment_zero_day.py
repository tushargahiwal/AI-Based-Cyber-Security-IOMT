"""§9.3 zero-day evaluation — leave-one-attack-family-out.

The claim the project rests on is that Stage 3 catches attacks the supervised
models were never trained on. Reporting accuracy on a test split cannot support
that claim: those attacks appear in training too, just as different rows. The
only honest test is to remove an entire attack family from training and see what
survives.

Protocol, per family:
  1. Remove every row of that family from the training and validation splits.
  2. Fit the supervised models (M1 RF, M2 XGB) on what is left.
  3. Fit the unsupervised models (M5 Isolation Forest, M7 One-Class SVM) on the
     benign training rows — unchanged, since they never see attacks anyway.
  4. Score the held-out family. The supervised models are meeting it for the
     first time; that is the zero-day.

The autoencoder (M4) is not refitted here: its shipped weights were already
trained on benign rows only, so it is already blind to both families and its
number carries over unchanged.

Run: cd ml && ../backend/venv/Scripts/python.exe experiment_zero_day.py
"""

import json
import time

import numpy as np
import pandas as pd
from sklearn.ensemble import IsolationForest, RandomForestClassifier
from sklearn.preprocessing import StandardScaler
from sklearn.svm import OneClassSVM
from xgboost import XGBClassifier

import preprocessing

RAW_PATH = "../data/raw/wustl-ehms-2020.csv"
PROCESSED_DIR = "../data/processed"
MODELS_DIR = "../models"

BENIGN_PERCENTILE = 97.5  # same benign false-positive budget as the shipped Stage 3


def prepared_frame():
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
    return X, raw["Label"].astype(int), raw["Attack Category"]


def main():
    print("Loading the raw capture and rebuilding the feature matrix...")
    X, y, family = prepared_frame()
    idx = np.load(f"{PROCESSED_DIR}/split_indices.npz")
    train_idx, test_idx = idx["train_idx"], idx["test_idx"]

    families = sorted(f for f in family.unique() if f.lower() != "normal")
    print(f"  attack families in this capture: {families}")
    print(f"  splits: train={len(train_idx)} test={len(test_idx)}")

    results = {}
    for held_out in families:
        print(f"\n{'=' * 74}\nHOLDING OUT: {held_out}\n{'=' * 74}")

        # Training sees benign + every OTHER family. Nothing of the held-out
        # family reaches any supervised model.
        train_mask = pd.Index(train_idx)
        keep = [i for i in train_mask if family.loc[i] != held_out]
        removed = len(train_mask) - len(keep)
        print(f"  removed {removed} '{held_out}' rows from training "
              f"({len(keep)} remain)")

        scaler = StandardScaler().fit(X.loc[keep])
        X_train = scaler.transform(X.loc[keep])
        y_train = y.loc[keep]

        # The zero-day set: held-out-family rows from the test split only, so no
        # row the models were fitted on can appear here.
        zero_day_idx = [i for i in test_idx if family.loc[i] == held_out]
        benign_test_idx = [i for i in test_idx if y.loc[i] == 0]
        X_zero = scaler.transform(X.loc[zero_day_idx])
        X_benign_test = scaler.transform(X.loc[benign_test_idx])
        print(f"  zero-day set: {len(zero_day_idx)} unseen '{held_out}' flows; "
              f"{len(benign_test_idx)} benign flows for the false-positive rate")

        entry = {"training_rows_removed": removed, "zero_day_flows": len(zero_day_idx)}

        print("\n  supervised models (meeting this family for the first time):")
        for name, model in [
            ("random_forest_M1", RandomForestClassifier(
                n_estimators=200, max_depth=25, min_samples_split=5, min_samples_leaf=2,
                max_features="sqrt", class_weight="balanced_subsample",
                n_jobs=-1, random_state=42)),
            ("xgboost_M2", XGBClassifier(
                n_estimators=300, max_depth=6, learning_rate=0.1, subsample=0.8,
                colsample_bytree=0.8, eval_metric="logloss", random_state=42, n_jobs=-1)),
        ]:
            model.fit(X_train, y_train)
            caught = float((model.predict(X_zero) == 1).mean())
            fpr = float((model.predict(X_benign_test) == 1).mean())
            entry[name] = {"zero_day_detection_rate": caught, "benign_false_positive_rate": fpr}
            print(f"    {name:<20} caught {caught:>7.2%} of unseen attacks   "
                  f"(benign FPR {fpr:.2%})")

        print("\n  unsupervised models (benign-only, unaffected by the hold-out):")
        benign_train = X.loc[[i for i in keep if y.loc[i] == 0]]
        benign_train_scaled = scaler.transform(benign_train)
        for name, model in [
            ("isolation_forest_M5", IsolationForest(
                n_estimators=200, n_jobs=-1, random_state=42)),
            ("one_class_svm_M7", OneClassSVM(kernel="rbf", gamma="scale", nu=0.025)),
        ]:
            model.fit(benign_train_scaled)
            threshold = np.percentile(-model.score_samples(benign_train_scaled), BENIGN_PERCENTILE)
            caught = float((-model.score_samples(X_zero) > threshold).mean())
            fpr = float((-model.score_samples(X_benign_test) > threshold).mean())
            entry[name] = {"zero_day_detection_rate": caught, "benign_false_positive_rate": fpr}
            print(f"    {name:<20} caught {caught:>7.2%} of unseen attacks   "
                  f"(benign FPR {fpr:.2%})")

        # What the pipeline actually does: Stage 1 OR Stage 3 raises it.
        best_unsup = max(entry["isolation_forest_M5"]["zero_day_detection_rate"],
                         entry["one_class_svm_M7"]["zero_day_detection_rate"])
        best_sup = max(entry["random_forest_M1"]["zero_day_detection_rate"],
                       entry["xgboost_M2"]["zero_day_detection_rate"])
        entry["stage3_uplift"] = best_unsup - best_sup
        print(f"\n    best supervised {best_sup:.2%} vs best unsupervised {best_unsup:.2%} "
              f"-> Stage 3 contributes {entry['stage3_uplift']:+.2%}")

        results[held_out] = entry

    with open(f"{MODELS_DIR}/zero_day_results.json", "w") as f:
        json.dump({"protocol": "leave-one-attack-family-out", "results": results}, f, indent=2)

    print("\n" + "=" * 84)
    print("§9.3 ZERO-DAY — detection of an attack family removed from training")
    print("=" * 84)
    print(f"{'Held-out family':<20}{'M1 RF':>10}{'M2 XGB':>10}{'M5 iForest':>13}{'M7 OC-SVM':>12}")
    for held_out, e in results.items():
        print(f"{held_out:<20}"
              f"{e['random_forest_M1']['zero_day_detection_rate']:>10.2%}"
              f"{e['xgboost_M2']['zero_day_detection_rate']:>10.2%}"
              f"{e['isolation_forest_M5']['zero_day_detection_rate']:>13.2%}"
              f"{e['one_class_svm_M7']['zero_day_detection_rate']:>12.2%}")
    print("=" * 84)
    print("Saved: models/zero_day_results.json")


if __name__ == "__main__":
    main()
