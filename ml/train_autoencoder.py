"""Stage 3 zero-day detector — M4 deep autoencoder, per doc §8.5. Architecture
widened from the doc's 28-input example to our actual 44-feature space, same
compression ratio (44 -> 32 -> 16 -> 8 -> 4 bottleneck -> mirror back to 44).

Trains on BENIGN ROWS FROM THE TRAIN SPLIT ONLY, calibrates the anomaly
threshold on the VAL split's benign rows, and evaluates on the TEST split
(benign + attack) — reusing preprocessing.py's split_indices.npz so this is
the exact same held-out test set Stage 1/2 were scored on, and none of it
leaked into training (doc §6.5 leakage rules).

Run: cd ml && ../backend/venv/Scripts/python.exe train_autoencoder.py
"""

import json

import joblib
import numpy as np
import pandas as pd
from sklearn.metrics import classification_report, confusion_matrix

import preprocessing as prep

SCALER_PATH = "../data/scalers/scaler_v1.pkl"
PROCESSED_DIR = "../data/processed"
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


def build_autoencoder(input_dim: int):
    import tensorflow as tf
    from tensorflow import keras

    model = keras.Sequential(
        [
            keras.layers.Input(shape=(input_dim,)),
            keras.layers.Dense(32, activation="relu"),
            keras.layers.Dense(16, activation="relu"),
            keras.layers.Dense(8, activation="relu"),
            keras.layers.Dense(4, activation="relu", name="bottleneck"),
            keras.layers.Dense(8, activation="relu"),
            keras.layers.Dense(16, activation="relu"),
            keras.layers.Dense(32, activation="relu"),
            keras.layers.Dense(input_dim, activation="linear"),
        ]
    )
    model.compile(optimizer=keras.optimizers.Adam(learning_rate=1e-3), loss="mse")
    return model


def main():
    import tensorflow as tf

    with open(f"{MODELS_DIR}/feature_order.json") as f:
        feature_cols = json.load(f)["features"]

    print("Rebuilding cleaned dataframe and reusing Stage 1's split indices...")
    df = build_clean_dataframe()
    splits = np.load(f"{PROCESSED_DIR}/split_indices.npz")
    train_df = df.loc[df.index.intersection(splits["train_idx"])]
    val_df = df.loc[df.index.intersection(splits["val_idx"])]
    test_df = df.loc[df.index.intersection(splits["test_idx"])]

    benign_train = train_df[train_df[prep.LABEL_COLUMN] == 0]
    benign_val = val_df[val_df[prep.LABEL_COLUMN] == 0]
    print(f"benign_train={len(benign_train)} (attack rows entirely excluded from training)")
    print(f"benign_val={len(benign_val)} (used only for threshold calibration)")
    print(f"test={len(test_df)} ({(test_df[prep.LABEL_COLUMN] == 0).sum()} benign, "
          f"{(test_df[prep.LABEL_COLUMN] == 1).sum()} attack)")

    scaler = joblib.load(SCALER_PATH)
    X_train = scaler.transform(benign_train[feature_cols])
    X_val = scaler.transform(benign_val[feature_cols])
    X_test = scaler.transform(test_df[feature_cols])
    y_test = test_df[prep.LABEL_COLUMN].values

    model = build_autoencoder(len(feature_cols))
    model.summary()

    early_stop = tf.keras.callbacks.EarlyStopping(monitor="val_loss", patience=10, restore_best_weights=True)
    model.fit(
        X_train, X_train,
        validation_data=(X_val, X_val),
        epochs=100,
        batch_size=64,
        callbacks=[early_stop],
        verbose=2,
    )

    print("\nCalibrating threshold on benign validation reconstruction error...")
    recon_val = model.predict(X_val, verbose=0)
    errors_val = np.mean(np.square(X_val - recon_val), axis=1)
    threshold = float(np.percentile(errors_val, 97.5))
    print(f"threshold (97.5th percentile) = {threshold:.6f}")

    print("\nEvaluating as a standalone anomaly detector on the held-out test split...")
    recon_test = model.predict(X_test, verbose=0)
    errors_test = np.mean(np.square(X_test - recon_test), axis=1)
    anomaly_scores = errors_test / threshold
    is_anomaly = (anomaly_scores > 1.0).astype(int)

    print(classification_report(y_test, is_anomaly, target_names=["benign", "attack"], zero_division=0))
    cm = confusion_matrix(y_test, is_anomaly)
    print(f"confusion matrix [[TN FP] [FN TP]]:\n{cm}")

    zero_day_recall = cm[1, 1] / (cm[1, 0] + cm[1, 1]) if (cm[1, 0] + cm[1, 1]) > 0 else 0.0
    false_positive_rate = cm[0, 1] / (cm[0, 0] + cm[0, 1]) if (cm[0, 0] + cm[0, 1]) > 0 else 0.0
    print(f"\nAnomaly-only detection rate on attacks (recall): {zero_day_recall:.4f}")
    print(f"False positive rate on benign traffic:            {false_positive_rate:.4f}")

    print("\nSaving artifact...")
    model.save(f"{MODELS_DIR}/autoencoder_v1.keras")
    with open(f"{MODELS_DIR}/autoencoder_results.json", "w") as f:
        json.dump(
            {
                "threshold": threshold,
                "percentile": 97.5,
                "test_detection_rate": zero_day_recall,
                "test_false_positive_rate": false_positive_rate,
                "confusion_matrix": cm.tolist(),
            },
            f,
            indent=2,
        )
    print("Saved: models/autoencoder_v1.keras, models/autoencoder_results.json")


if __name__ == "__main__":
    main()
