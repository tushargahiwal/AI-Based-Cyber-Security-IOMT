"""Loads trained model/scaler artifacts and runs Stage 1 inference.

Artifact paths stored in ml_models.artifact_path / .scaler_path are relative
to the project root (e.g. "models/binary_rf_v1.pkl"), matching how ml/*.py
scripts save them — this file resolves them relative to that same root.
"""

import json
import warnings
from pathlib import Path

import joblib
import numpy as np

_PROJECT_ROOT = Path(__file__).resolve().parents[2]  # backend/services/.. -> backend/.. -> project root
_FEATURE_ORDER_PATH = _PROJECT_ROOT / "models" / "feature_order.json"
_VITALS_RESULTS_PATH = _PROJECT_ROOT / "models" / "vitals_lstm_results.json"

# The estimators were fit on named DataFrame columns; we score bare arrays.
# Passing a DataFrame instead would silence this at 3.5x the latency (8 ms ->
# 28 ms per flow), and column order is already guaranteed the strict way: every
# vector is built against models/feature_order.json, and workers/replay.py's
# vectors were checked to match the training matrix exactly.
warnings.filterwarnings(
    "ignore",
    message="X does not have valid feature names",
    category=UserWarning,
    module="sklearn",
)

_model_cache: dict[str, object] = {}
_scaler_cache: dict[str, object] = {}
_keras_model_cache: dict[str, object] = {}
_keras_callable_cache: dict[str, object] = {}
_feature_order_cache: dict | None = None
_vitals_meta_cache: dict | None = None


def _load_feature_order() -> dict:
    global _feature_order_cache
    if _feature_order_cache is None:
        with open(_FEATURE_ORDER_PATH) as f:
            _feature_order_cache = json.load(f)
    return _feature_order_cache


def get_expected_features(feature_set_version: str) -> list[str]:
    data = _load_feature_order()
    if data["feature_set_version"] != feature_set_version:
        raise ValueError(
            f"unknown feature_set_version '{feature_set_version}' "
            f"(pipeline currently produces '{data['feature_set_version']}')"
        )
    return data["features"]


def _load_artifact(cache: dict, relative_path: str):
    if relative_path not in cache:
        artifact = joblib.load(_PROJECT_ROOT / relative_path)
        # A forest trained with n_jobs=-1 keeps that setting when pickled, and
        # fanning 200 trees across a thread pool to score ONE row costs far more
        # in dispatch than the trees do: 93 ms against 8 ms single-threaded.
        # Every call here scores exactly one flow.
        if getattr(artifact, "n_jobs", None) not in (None, 1):
            artifact.n_jobs = 1
        cache[relative_path] = artifact
    return cache[relative_path]


def _keras_forward(relative_path: str, X: np.ndarray) -> np.ndarray:
    """Single-sample forward pass through a cached, graph-compiled callable.

    Both Keras stages score exactly one sample per flow, where .predict()'s
    batching machinery is pure overhead. Measured per call on this hardware:

        autoencoder   .predict() 150 ms   eager  14 ms   tf.function  1.3 ms
        vitals LSTM   .predict() 139 ms   eager 319 ms   tf.function  5.6 ms

    Note the LSTM is *slower* called eagerly than through .predict() — its
    30-step recurrence is exactly what graph compilation exists to fix — so
    dropping .predict() alone would have made Stage 4 worse. The compiled
    function is cached per artifact; building it is what costs, not calling it.
    """
    fn = _keras_callable_cache.get(relative_path)
    if fn is None:
        import tensorflow as tf

        model = _load_keras_model(relative_path)

        @tf.function(reduce_retracing=True)
        def forward(x):
            return model(x, training=False)

        fn = forward
        _keras_callable_cache[relative_path] = fn
    return np.asarray(fn(X.astype("float32")))


def _load_keras_model(relative_path: str):
    # Lazy import — TensorFlow is only needed once Stage 3 actually runs,
    # keeping it off the hot path for requests that never touch the autoencoder.
    if relative_path not in _keras_model_cache:
        from tensorflow import keras

        _keras_model_cache[relative_path] = keras.models.load_model(_PROJECT_ROOT / relative_path)
    return _keras_model_cache[relative_path]


def load_model(relative_path: str):
    """Shared access to the cached estimators — explanation_service needs the
    same object the detection ran on, not a second copy loaded from disk."""
    return _load_artifact(_model_cache, relative_path)


def load_scaler(relative_path: str):
    return _load_artifact(_scaler_cache, relative_path)


def run_stage1(*, artifact_path: str, scaler_path: str, feature_vector: list[float]) -> dict:
    model = _load_artifact(_model_cache, artifact_path)
    scaler = _load_artifact(_scaler_cache, scaler_path)

    X = np.array(feature_vector, dtype=float).reshape(1, -1)
    X_scaled = scaler.transform(X)
    probability = float(model.predict_proba(X_scaled)[0][1])
    label = "malicious" if probability >= 0.5 else "benign"
    return {"label": label, "probability": probability}


def run_stage2(*, artifact_path: str, scaler_path: str, feature_vector: list[float], output_classes: list[str]) -> dict:
    model = _load_artifact(_model_cache, artifact_path)
    scaler = _load_artifact(_scaler_cache, scaler_path)  # same scaler as Stage 1 -> cache hit, not re-loaded

    X = np.array(feature_vector, dtype=float).reshape(1, -1)
    X_scaled = scaler.transform(X)
    probs = model.predict_proba(X_scaled)[0]
    class_idx = int(np.argmax(probs))
    return {
        "family": output_classes[class_idx],
        "confidence": float(probs[class_idx]),
        "class_probabilities": {cls: float(p) for cls, p in zip(output_classes, probs)},
    }


def run_stage3(*, artifact_path: str, scaler_path: str, feature_vector: list[float], threshold: float) -> dict:
    scaler = _load_artifact(_scaler_cache, scaler_path)

    X = np.array(feature_vector, dtype=float).reshape(1, -1)
    X_scaled = scaler.transform(X)
    reconstruction = _keras_forward(artifact_path, X_scaled)
    reconstruction_error = float(np.mean(np.square(X_scaled - reconstruction)))
    anomaly_score = reconstruction_error / threshold if threshold else 0.0
    return {
        "reconstruction_error": reconstruction_error,
        "anomaly_score": anomaly_score,
        "is_anomaly": anomaly_score > 1.0,
    }


def _load_vitals_meta() -> dict:
    """vitals_order / window / residual_std, written by ml/train_vitals_lstm.py."""
    global _vitals_meta_cache
    if _vitals_meta_cache is None:
        with open(_VITALS_RESULTS_PATH) as f:
            _vitals_meta_cache = json.load(f)
    return _vitals_meta_cache


def get_vitals_order() -> list[str]:
    return _load_vitals_meta()["vitals_order"]


def get_vitals_window() -> int:
    return _load_vitals_meta()["window"]


def run_stage4(*, artifact_path: str, scaler_path: str, window: list[list[float]], threshold: float) -> dict:
    """Stage 4 physiological plausibility.

    `window` is WINDOW+1 readings, oldest first: the first WINDOW feed the LSTM,
    the last one is the reading actually observed. Per-vital residuals are divided
    by the benign residual_std captured at training time, so `threshold` is a
    z-score (3.0 is what ml/train_vitals_lstm.py evaluates against), not a raw error.
    """
    meta = _load_vitals_meta()
    n_steps = meta["window"]
    vitals_order = meta["vitals_order"]
    residual_std = np.array(meta["residual_std"], dtype=float)

    if len(window) != n_steps + 1:
        raise ValueError(f"stage 4 needs {n_steps + 1} readings (got {len(window)})")

    scaler = _load_artifact(_scaler_cache, scaler_path)  # vitals scaler, not the flow-feature one

    scaled = scaler.transform(np.array(window, dtype=float))
    X = scaled[:n_steps].reshape(1, n_steps, len(vitals_order))
    actual = scaled[n_steps]

    predicted = _keras_forward(artifact_path, X)[0]
    z_scores = np.abs(actual - predicted) / residual_std
    max_idx = int(np.argmax(z_scores))

    # Predictions are reported in original units so the UI can show them next to
    # the observed reading; inverse_transform needs a full 2-D row.
    predicted_raw = scaler.inverse_transform(predicted.reshape(1, -1))[0]

    return {
        "max_zscore": float(z_scores[max_idx]),
        "worst_vital": vitals_order[max_idx],
        "zscores": {v: float(z) for v, z in zip(vitals_order, z_scores)},
        "predicted_values": {v: float(p) for v, p in zip(vitals_order, predicted_raw)},
        "injection_suspected": bool(z_scores[max_idx] > threshold),
    }
