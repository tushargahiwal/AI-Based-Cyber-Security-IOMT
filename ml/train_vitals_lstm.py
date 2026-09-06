"""Stage 4 physiological plausibility — M6 LSTM vitals forecaster, per doc §8.7.

Unlike M1/M2/M4, this runs on the VITALS STREAM, not network flow features —
6 vitals per reading (Heart_rate, SpO2, SYS, DIA, Temp, Resp_Rate), predicting
the next reading from the previous 30. Trained on benign sequences only.

WUSTL-EHMS-2020 has no explicit per-row timestamp, but the CSV's row order IS
the capture order, and Label/Attack Category come in contiguous blocks (85
benign runs, mean length ~168 rows) — confirmed by inspection, not assumed.
We build sliding 30-step windows from benign runs only (run length >= 31),
split at the RUN level so no window straddles train/val/test.

Run: cd ml && ../backend/venv/Scripts/python.exe train_vitals_lstm.py
"""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.preprocessing import StandardScaler

VITALS = ["Heart_rate", "SpO2", "SYS", "DIA", "Temp", "Resp_Rate"]
WINDOW = 30
RAW_PATH = "../data/raw/wustl-ehms-2020.csv"
SCALER_DIR = "../data/scalers"
MODELS_DIR = "../models"


def find_runs(labels: np.ndarray) -> list[tuple[int, int, int]]:
    """Returns (label, start_idx, length) for each contiguous run, in order."""
    runs = []
    start = 0
    current = labels[0]
    for i in range(1, len(labels)):
        if labels[i] != current:
            runs.append((int(current), start, i - start))
            start = i
            current = labels[i]
    runs.append((int(current), start, len(labels) - start))
    return runs


def build_windows(df: pd.DataFrame, run_indices: list[tuple[int, int]]) -> np.ndarray:
    """run_indices: list of (start, length) into df, already benign-only, length >= WINDOW+1."""
    X = df[VITALS].to_numpy(dtype=float)
    windows = []
    for start, length in run_indices:
        run = X[start:start + length]
        for i in range(len(run) - WINDOW):
            windows.append(run[i:i + WINDOW + 1])  # 30 input + 1 target
    return np.array(windows)


def build_autoencoder_lstm(n_vitals: int):
    from tensorflow import keras

    model = keras.Sequential([
        keras.layers.Input(shape=(WINDOW, n_vitals)),
        keras.layers.LSTM(64, return_sequences=True),
        keras.layers.Dropout(0.2),
        keras.layers.LSTM(32),
        keras.layers.Dropout(0.2),
        keras.layers.Dense(16, activation="relu"),
        keras.layers.Dense(n_vitals, activation="linear"),
    ])
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=1e-3), loss="mse")
    return model


def main():
    import tensorflow as tf

    print("Loading raw CSV in original capture order (row order matters here)...")
    df = pd.read_csv(RAW_PATH)

    print("Imputing sensor dropouts (0-value readings) via forward-fill within the file...")
    for v in VITALS:
        df[v] = df[v].replace(0, np.nan).ffill().bfill()

    runs = find_runs(df["Label"].to_numpy())
    benign_runs = [(start, length) for label, start, length in runs if label == 0 and length >= WINDOW + 1]
    attack_runs = [(start, length) for label, start, length in runs if label == 1]
    print(f"{len(benign_runs)} usable benign runs (length >= {WINDOW + 1}), "
          f"{len(runs) - len(benign_runs) - len(attack_runs)} benign runs too short to use")
    print(f"{len(attack_runs)} attack runs (for evaluation only, never for training)")

    # split at the RUN level so no sliding window straddles train/val/test
    rng = np.random.RandomState(42)
    order = rng.permutation(len(benign_runs))
    n_train = int(0.7 * len(order))
    n_val = int(0.15 * len(order))
    train_runs = [benign_runs[i] for i in order[:n_train]]
    val_runs = [benign_runs[i] for i in order[n_train:n_train + n_val]]
    test_runs = [benign_runs[i] for i in order[n_train + n_val:]]
    print(f"runs: train={len(train_runs)} val={len(val_runs)} test={len(test_runs)}")

    train_windows = build_windows(df, train_runs)
    val_windows = build_windows(df, val_runs)
    test_windows = build_windows(df, test_runs)
    print(f"windows: train={len(train_windows)} val={len(val_windows)} test={len(test_windows)}")

    scaler = StandardScaler()
    flat_train = train_windows.reshape(-1, len(VITALS))
    scaler.fit(flat_train)

    def scale(windows):
        shape = windows.shape
        return scaler.transform(windows.reshape(-1, len(VITALS))).reshape(shape)

    train_s, val_s, test_s = scale(train_windows), scale(val_windows), scale(test_windows)
    X_train, y_train = train_s[:, :WINDOW, :], train_s[:, WINDOW, :]
    X_val, y_val = val_s[:, :WINDOW, :], val_s[:, WINDOW, :]
    X_test, y_test = test_s[:, :WINDOW, :], test_s[:, WINDOW, :]

    model = build_autoencoder_lstm(len(VITALS))
    model.summary()

    early_stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=8, restore_best_weights=True)
    model.fit(
        X_train, y_train,
        validation_data=(X_val, y_val),
        epochs=60,
        batch_size=64,
        callbacks=[early_stop],
        verbose=2,
    )

    print("\nComputing residual std per vital on benign validation set (for z-score normalisation)...")
    pred_val = model.predict(X_val, verbose=0)
    residuals_val = np.abs(y_val - pred_val)
    residual_std = residuals_val.std(axis=0)
    residual_std = np.where(residual_std < 1e-6, 1e-6, residual_std)  # guard divide-by-zero
    print("residual_std (scaled space):", dict(zip(VITALS, residual_std.tolist())))

    def z_scores(X, y):
        pred = model.predict(X, verbose=0)
        residuals = np.abs(y - pred)
        return residuals / residual_std

    print("\nEvaluating on held-out BENIGN test windows (expect few flags)...")
    z_test_benign = z_scores(X_test, y_test)
    benign_flagged = (z_test_benign.max(axis=1) > 3.0).mean()
    print(f"benign test windows flagged (z>3.0 on any vital): {benign_flagged:.4f}")

    print("\nEvaluating on windows ENDING inside an attack run (the actual injection detection test)...")
    attack_end_windows = []
    for start, length in attack_runs:
        if length >= 1 and start - WINDOW >= 0:
            window = df[VITALS].to_numpy(dtype=float)[start - WINDOW:start + 1]
            if len(window) == WINDOW + 1:
                attack_end_windows.append(window)
    if attack_end_windows:
        attack_arr = np.array(attack_end_windows)
        attack_s = scale(attack_arr)
        X_atk, y_atk = attack_s[:, :WINDOW, :], attack_s[:, WINDOW, :]
        z_attack = z_scores(X_atk, y_atk)
        attack_detection_rate = (z_attack.max(axis=1) > 3.0).mean()
        print(f"attack-boundary windows flagged (z>3.0 on any vital): {attack_detection_rate:.4f} "
              f"({len(attack_end_windows)} windows)")
    else:
        attack_detection_rate = None
        print("no attack-boundary windows available")

    print("\nSaving artifacts...")
    model.save(f"{MODELS_DIR}/vitals_lstm_v1.keras")
    joblib.dump(scaler, f"{SCALER_DIR}/vitals_scaler_v1.pkl")
    with open(f"{MODELS_DIR}/vitals_lstm_results.json", "w") as f:
        json.dump(
            {
                "vitals_order": VITALS,
                "window": WINDOW,
                "residual_std": residual_std.tolist(),
                "benign_test_false_positive_rate": float(benign_flagged),
                "attack_boundary_detection_rate": float(attack_detection_rate) if attack_detection_rate is not None else None,
            },
            f,
            indent=2,
        )
    print("Saved: models/vitals_lstm_v1.keras, data/scalers/vitals_scaler_v1.pkl, models/vitals_lstm_results.json")


if __name__ == "__main__":
    main()
