"""M3 — CNN-BiLSTM over flow windows, doc §8.4.

Every other model here judges one flow in isolation. A real intrusion is a
sequence: a scan, then an exploit attempt, then the payload. M3 reads a sliding
window of 10 consecutive flows so it can see that shape, with a 1-D convolution
picking up short local patterns and a bidirectional LSTM carrying context across
the whole window.

Two things decide whether this experiment is honest:

  1. Windows overlap by nine flows, so a random row-level split would put nearly
     identical windows in train and test and report a fantasy score. The split
     here is by contiguous BLOCK of the capture, and a gap of WINDOW-1 flows is
     dropped at each boundary so no single window spans two blocks.

  2. A window is labelled by its LAST flow — what the model would be asked in
     production, where only the past is available. Labelling by "any attack in
     the window" would let it score by looking ahead.

Run: cd ml && ../backend/venv/Scripts/python.exe train_cnn_bilstm.py
"""

import json
import time

import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix, f1_score
from sklearn.preprocessing import StandardScaler

import preprocessing

RAW_PATH = "../data/raw/wustl-ehms-2020.csv"
MODELS_DIR = "../models"
SCALER_DIR = "../data/scalers"

WINDOW = 10
CLASSES = ["normal", "Data Alteration", "Spoofing"]


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
    return X, raw["Attack Category"]


def windows_from_block(X: np.ndarray, y: np.ndarray, start: int, stop: int):
    """Sliding windows wholly inside [start, stop), labelled by the last flow."""
    xs, ys = [], []
    for end in range(start + WINDOW, stop + 1):
        xs.append(X[end - WINDOW:end])
        ys.append(y[end - 1])
    return np.array(xs, dtype="float32"), np.array(ys)


def build_model(n_features: int, n_classes: int):
    from tensorflow import keras

    return keras.Sequential([
        keras.layers.Input(shape=(WINDOW, n_features)),
        # Local pattern detector across time, then context in both directions.
        keras.layers.Conv1D(64, kernel_size=3, padding="same", activation="relu"),
        keras.layers.BatchNormalization(),
        keras.layers.Bidirectional(keras.layers.LSTM(64, return_sequences=True)),
        keras.layers.Dropout(0.3),
        keras.layers.Bidirectional(keras.layers.LSTM(32)),
        keras.layers.Dropout(0.3),
        keras.layers.Dense(64, activation="relu"),
        keras.layers.Dense(n_classes, activation="softmax"),
    ])


def main():
    import tensorflow as tf
    from tensorflow import keras

    print("Rebuilding the feature matrix in capture order...")
    X_df, family = prepared_frame()
    labels = family.map({name: i for i, name in enumerate(CLASSES)}).to_numpy()
    print(f"  {len(X_df)} flows, {X_df.shape[1]} features")
    print(f"  class counts: {dict(zip(*np.unique(family, return_counts=True)))}")

    n = len(X_df)
    train_stop = int(0.70 * n)
    val_stop = int(0.85 * n)
    print(f"\nBlock split (capture order preserved): "
          f"train[0:{train_stop}] val[{train_stop}:{val_stop}] test[{val_stop}:{n}]")

    # Scaling is fitted on the training block only.
    scaler = StandardScaler().fit(X_df.iloc[:train_stop])
    X = scaler.transform(X_df).astype("float32")

    # The +WINDOW-1 offsets are the boundary gap: a window starting inside one
    # block must not reach into the next, or the split leaks.
    X_train, y_train = windows_from_block(X, labels, 0, train_stop)
    X_val, y_val = windows_from_block(X, labels, train_stop + WINDOW - 1, val_stop)
    X_test, y_test = windows_from_block(X, labels, val_stop + WINDOW - 1, n)
    print(f"  windows: train={len(X_train)} val={len(X_val)} test={len(X_test)}")
    for split, y in [("train", y_train), ("val", y_val), ("test", y_test)]:
        present = {CLASSES[i]: int(c) for i, c in zip(*np.unique(y, return_counts=True))}
        print(f"    {split}: {present}")

    present_classes = sorted(set(y_train) | set(y_val) | set(y_test))
    if len(present_classes) < 2:
        raise SystemExit("the block split left fewer than two classes — nothing to learn")

    model = build_model(X.shape[1], len(CLASSES))
    model.compile(
        optimizer=keras.optimizers.Adam(learning_rate=1e-3),
        loss="sparse_categorical_crossentropy",
        metrics=["accuracy"],
    )
    model.summary()

    # Attack windows are the minority; without weighting the model can score well
    # by calling everything normal.
    counts = np.bincount(y_train, minlength=len(CLASSES))
    weights = {i: (len(y_train) / (len(CLASSES) * c)) if c else 0.0 for i, c in enumerate(counts)}
    print(f"\nclass weights: { {CLASSES[i]: round(w, 3) for i, w in weights.items()} }")

    print("\nTraining...")
    t0 = time.perf_counter()
    history = model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=40,
        batch_size=64,
        class_weight=weights,
        callbacks=[keras.callbacks.EarlyStopping(
            monitor="val_loss", patience=6, restore_best_weights=True)],
        verbose=2,
    )
    train_seconds = time.perf_counter() - t0

    print("\nEvaluating on the held-out block...")
    probabilities = model.predict(X_test, verbose=0)
    y_pred = probabilities.argmax(axis=1)

    present = sorted(set(y_test) | set(y_pred))
    names = [CLASSES[i] for i in present]
    report = classification_report(
        y_test, y_pred, labels=present, target_names=names, output_dict=True, zero_division=0
    )
    print(classification_report(y_test, y_pred, labels=present, target_names=names, zero_division=0))

    macro_f1 = float(f1_score(y_test, y_pred, average="macro", zero_division=0))
    print(f"macro F1: {macro_f1:.4f}")

    model.save(f"{MODELS_DIR}/cnn_bilstm_v1.keras")
    import joblib
    joblib.dump(scaler, f"{SCALER_DIR}/cnn_bilstm_scaler_v1.pkl")
    with open(f"{MODELS_DIR}/cnn_bilstm_results.json", "w") as f:
        json.dump({
            "window": WINDOW,
            "classes": CLASSES,
            "split": "contiguous blocks 70/15/15 with a WINDOW-1 gap at each boundary",
            "label_rule": "the window takes the label of its LAST flow",
            "train_seconds": train_seconds,
            "epochs_run": len(history.history["loss"]),
            "macro_f1": macro_f1,
            "classification_report": report,
            "confusion_matrix": confusion_matrix(y_test, y_pred, labels=present).tolist(),
            "confusion_matrix_labels": names,
        }, f, indent=2)

    print("\nSaved: models/cnn_bilstm_v1.keras, data/scalers/cnn_bilstm_scaler_v1.pkl,")
    print("       models/cnn_bilstm_results.json")


if __name__ == "__main__":
    main()
