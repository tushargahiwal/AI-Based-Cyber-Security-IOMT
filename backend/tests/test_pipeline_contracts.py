"""Contracts between the trained artifacts and the code that serves them.

These read the real files in models/ and data/scalers/. If a model is retrained
and the feature order, vitals order or input width shifts, the pipeline would
otherwise keep running and quietly score garbage — these fail instead.
"""

import json
from pathlib import Path

import numpy as np
import pytest

from services import explanation_service, inference_service

PROJECT_ROOT = Path(__file__).resolve().parents[2]


def test_feature_order_matches_what_stage1_was_trained_on():
    features = inference_service.get_expected_features("v1")
    model = inference_service.load_model("models/binary_rf_v1.pkl")
    scaler = inference_service.load_scaler("data/scalers/scaler_v1.pkl")

    assert len(features) == model.n_features_in_ == scaler.n_features_in_
    assert list(scaler.feature_names_in_) == features


def test_an_unknown_feature_set_version_is_refused():
    with pytest.raises(ValueError, match="unknown feature_set_version"):
        inference_service.get_expected_features("v99")


def test_vitals_metadata_agrees_with_the_lstm_it_describes():
    meta = json.loads((PROJECT_ROOT / "models" / "vitals_lstm_results.json").read_text())
    assert len(meta["residual_std"]) == len(meta["vitals_order"])
    assert all(s > 0 for s in meta["residual_std"]), "a zero std would divide by zero"

    scaler = inference_service.load_scaler("data/scalers/vitals_scaler_v1.pkl")
    assert scaler.n_features_in_ == len(meta["vitals_order"])
    assert inference_service.get_vitals_window() == meta["window"]


def test_scoring_is_deterministic():
    """The same flow must never produce two different verdicts.

    Stage 3 runs a Keras model through a cached tf.function; if that cache were
    ever keyed wrongly, or a model were reloaded per call, this is where the
    drift would show.
    """
    vector = [1.0] * len(inference_service.get_expected_features("v1"))
    args = dict(
        artifact_path="models/autoencoder_v1.keras",
        scaler_path="data/scalers/scaler_v1.pkl",
        threshold=0.3376,
    )
    first = inference_service.run_stage3(feature_vector=vector, **args)
    second = inference_service.run_stage3(feature_vector=vector, **args)
    assert first == second


def test_stage1_probability_and_label_agree():
    vector = [0.0] * len(inference_service.get_expected_features("v1"))
    result = inference_service.run_stage1(
        artifact_path="models/binary_rf_v1.pkl",
        scaler_path="data/scalers/scaler_v1.pkl",
        feature_vector=vector,
    )
    assert 0.0 <= result["probability"] <= 1.0
    assert result["label"] == ("malicious" if result["probability"] >= 0.5 else "benign")


def test_forests_are_loaded_single_threaded():
    """Scoring one row across a thread pool costs ~10x more in dispatch."""
    model = inference_service.load_model("models/binary_rf_v1.pkl")
    assert model.n_jobs == 1


@pytest.mark.parametrize(
    "shap_output, expected_value, expected_contributions, expected_base",
    [
        # a list of one array per class (older shap)
        ([np.array([[0.1, -0.2]]), np.array([[0.3, -0.4]])], [0.4, 0.6], [0.3, -0.4], 0.6),
        # a single (1, n_features, n_classes) array (shap >= 0.45)
        (np.array([[[0.1, 0.3], [-0.2, -0.4]]]), [0.4, 0.6], [0.3, -0.4], 0.6),
        # a plain (1, n_features) array for a single-output model
        (np.array([[0.3, -0.4]]), 0.6, [0.3, -0.4], 0.6),
    ],
)
def test_shap_output_shapes_are_all_handled(shap_output, expected_value,
                                            expected_contributions, expected_base):
    """TreeExplainer's return shape has changed across shap releases."""
    contributions, base = explanation_service._malicious_class_slice(
        shap_output, expected_value, class_index=1
    )
    assert np.allclose(contributions, expected_contributions)
    assert base == pytest.approx(expected_base)
