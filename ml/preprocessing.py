"""Preprocessing pipeline for WUSTL-EHMS-2020 — follows the exact order in
docs/IoMT_Attack_Detection_Build_Document.pdf §7.4. Do not reorder the steps;
later stages (SMOTE, scaling) assume the earlier ones already ran.

Run: cd ml && ../backend/venv/Scripts/python.exe preprocessing.py
"""

import json

import numpy as np
import pandas as pd
from imblearn.over_sampling import SMOTE
from sklearn.model_selection import train_test_split
from sklearn.preprocessing import LabelEncoder, StandardScaler

RAW_PATH = "../data/raw/wustl-ehms-2020.csv"
PROCESSED_DIR = "../data/processed"
SCALER_DIR = "../data/scalers"
MODELS_DIR = "../models"

# Row/packet identifiers — not predictive, and would let the model memorise
# specific hosts instead of learning attack behaviour (doc §6.5 leakage rules).
IDENTIFIER_COLUMNS = ["SrcAddr", "DstAddr", "SrcMac", "DstMac", "Packet_num"]
CATEGORICAL_COLUMNS = ["Dir", "Flgs"]
LABEL_COLUMN = "Label"
ATTACK_FAMILY_COLUMN = "Attack Category"  # kept aside for later multiclass work, not fed to the binary model


def load_raw() -> pd.DataFrame:
    return pd.read_csv(RAW_PATH)


def drop_identifiers(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop(columns=[c for c in IDENTIFIER_COLUMNS if c in df.columns])


def coerce_numeric_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Sport is mostly numeric but Argus (the flow-capture tool this dataset
    was built with) occasionally resolves a well-known port to its service
    name (e.g. 'fido', 'tfido') instead of the number. Force numeric; the few
    unparseable rows become NaN and get median-imputed like any other gap.
    """
    for col in ("Sport", "Dport"):
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    return df


def handle_infinities(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    df[numeric_cols] = df[numeric_cols].replace([np.inf, -np.inf], np.nan)
    return df


def impute(df: pd.DataFrame) -> pd.DataFrame:
    numeric_cols = df.select_dtypes(include=[np.number]).columns
    categorical_cols = df.select_dtypes(exclude=[np.number]).columns
    for col in numeric_cols:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].median())
    for col in categorical_cols:
        if df[col].isnull().any():
            df[col] = df[col].fillna(df[col].mode(dropna=True)[0])
    return df


def drop_duplicates(df: pd.DataFrame) -> pd.DataFrame:
    return df.drop_duplicates()


def winsorize(df: pd.DataFrame, exclude: list) -> pd.DataFrame:
    numeric_cols = [c for c in df.select_dtypes(include=[np.number]).columns if c not in exclude]
    for col in numeric_cols:
        lo, hi = df[col].quantile(0.01), df[col].quantile(0.99)
        df[col] = df[col].clip(lo, hi)
    return df


def encode(df: pd.DataFrame):
    df = pd.get_dummies(df, columns=[c for c in CATEGORICAL_COLUMNS if c in df.columns])
    attack_family_encoder = LabelEncoder()
    df["attack_family_encoded"] = attack_family_encoder.fit_transform(df[ATTACK_FAMILY_COLUMN])
    return df, attack_family_encoder


def main():
    print("1. Loading raw CSV...")
    df = load_raw()
    print(f"   {df.shape[0]} rows, {df.shape[1]} columns")

    print("2. Dropping identifier columns...")
    df = drop_identifiers(df)

    print("2b. Coercing Sport/Dport to numeric...")
    df = coerce_numeric_columns(df)

    print("3. Handling infinities...")
    df = handle_infinities(df)

    print("4. Imputing NaN...")
    df = impute(df)

    print("5. Removing exact duplicate rows...")
    before = len(df)
    df = drop_duplicates(df)
    print(f"   dropped {before - len(df)} duplicates")

    print("6. Winsorising at 1st/99th percentile...")
    df = winsorize(df, exclude=[LABEL_COLUMN])

    print("7. Encoding categoricals + label...")
    df, attack_family_encoder = encode(df)

    feature_cols = [
        c for c in df.columns if c not in (LABEL_COLUMN, ATTACK_FAMILY_COLUMN, "attack_family_encoded")
    ]
    X = df[feature_cols]
    y = df[LABEL_COLUMN].astype(int)

    print("8. Stratified 70/15/15 split...")
    X_train, X_temp, y_train, y_temp = train_test_split(
        X, y, test_size=0.30, stratify=y, random_state=42
    )
    X_val, X_test, y_val, y_test = train_test_split(
        X_temp, y_temp, test_size=0.50, stratify=y_temp, random_state=42
    )
    print(f"   train={len(X_train)} val={len(X_val)} test={len(X_test)}")

    print("9. Fitting StandardScaler on train only...")
    scaler = StandardScaler()
    X_train_scaled = pd.DataFrame(scaler.fit_transform(X_train), columns=feature_cols, index=X_train.index)
    X_val_scaled = pd.DataFrame(scaler.transform(X_val), columns=feature_cols, index=X_val.index)
    X_test_scaled = pd.DataFrame(scaler.transform(X_test), columns=feature_cols, index=X_test.index)

    print("10. SMOTE on training split only...")
    print(f"    before: {y_train.value_counts().to_dict()}")
    smote = SMOTE(random_state=42)
    X_train_res, y_train_res = smote.fit_resample(X_train_scaled, y_train)
    print(f"    after:  {y_train_res.value_counts().to_dict()}")

    print("11. Saving splits, scaler, feature order...")
    import os

    os.makedirs(PROCESSED_DIR, exist_ok=True)
    os.makedirs(SCALER_DIR, exist_ok=True)
    os.makedirs(MODELS_DIR, exist_ok=True)

    X_train_res.to_csv(f"{PROCESSED_DIR}/X_train.csv", index=False)
    y_train_res.to_csv(f"{PROCESSED_DIR}/y_train.csv", index=False)
    X_val_scaled.to_csv(f"{PROCESSED_DIR}/X_val.csv", index=False)
    y_val.to_csv(f"{PROCESSED_DIR}/y_val.csv", index=False)
    X_test_scaled.to_csv(f"{PROCESSED_DIR}/X_test.csv", index=False)
    y_test.to_csv(f"{PROCESSED_DIR}/y_test.csv", index=False)

    import joblib

    joblib.dump(scaler, f"{SCALER_DIR}/scaler_v1.pkl")
    joblib.dump(attack_family_encoder, f"{SCALER_DIR}/attack_family_encoder_v1.pkl")

    with open(f"{MODELS_DIR}/feature_order.json", "w") as f:
        json.dump({"feature_set_version": "v1", "features": feature_cols}, f, indent=2)

    np.savez(
        f"{PROCESSED_DIR}/split_indices.npz",
        train_idx=X_train.index.to_numpy(),
        val_idx=X_val.index.to_numpy(),
        test_idx=X_test.index.to_numpy(),
    )

    print(f"\nDone. {len(feature_cols)} features.")


if __name__ == "__main__":
    main()
