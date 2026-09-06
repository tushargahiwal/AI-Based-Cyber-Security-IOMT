"""SHAP explanations for a Stage 1 verdict (doc §12, Module 6).

An analyst being told "this flow is 95% malicious" cannot act on that; they need
to know which of the 44 flow features drove it. Stage 1 is a random forest, so
shap.TreeExplainer gives exact per-feature contributions cheaply — no sampling,
no background dataset.

Explanations are computed on demand and stored, because a detection's inputs and
model never change after the fact: recomputing would always give the same answer.
"""

import numpy as np
from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.detection import Detection
from models.explanation import Explanation
from models.flow_feature import FlowFeature
from models.ml_model import MlModel
from services import inference_service

TOP_N = 8

_explainer_cache: dict[str, object] = {}


def _get_explainer(artifact_path: str):
    if artifact_path not in _explainer_cache:
        # Imported lazily: shap pulls in a large dependency tree and most
        # requests never ask for an explanation.
        import shap

        model = inference_service.load_model(artifact_path)
        _explainer_cache[artifact_path] = shap.TreeExplainer(model)
    return _explainer_cache[artifact_path]


def _malicious_class_slice(values, expected_value, class_index: int):
    """Pull the malicious-class column out of whatever shape shap returned.

    TreeExplainer on a binary classifier has returned three different shapes
    across shap versions: a list of one array per class, a single (1, n, 2)
    array, or a plain (1, n) array when the model has a single output.
    """
    if isinstance(values, list):
        contributions = np.asarray(values[class_index])[0]
        base = np.asarray(expected_value)[class_index]
    else:
        values = np.asarray(values)
        if values.ndim == 3:
            contributions = values[0, :, class_index]
            base = np.asarray(expected_value)[class_index]
        else:
            contributions = values[0]
            base = np.asarray(expected_value).ravel()[0]
    return np.asarray(contributions, dtype=float), float(base)


def _narrative(*, probability: float, verdict: str, ranked: list[dict]) -> str:
    pushed_up = [f for f in ranked if f["contribution"] > 0][:3]
    pushed_down = [f for f in ranked if f["contribution"] < 0][:2]

    def named(features: list[dict]) -> str:
        # One-hot column names come out of pandas padded ("Flgs_ e        ");
        # that padding is noise in a sentence.
        return ", ".join(f"{f['feature'].strip()} = {f['value']:g}" for f in features)

    parts = [
        f"Stage 1 scored this flow {probability:.1%} malicious (verdict: {verdict.replace('_', ' ')})."
    ]
    if pushed_up:
        parts.append(f"What pushed it toward malicious, strongest first: {named(pushed_up)}.")
    else:
        parts.append("Nothing in this flow's top features pushed it toward malicious.")
    if pushed_down:
        lead = "Pulling the other way" if pushed_up else "The strongest evidence it is benign"
        parts.append(f"{lead}: {named(pushed_down)}.")
    parts.append(
        "Contributions are SHAP values on the Stage 1 random forest and sum to the gap "
        "between this flow's score and the average flow's."
    )
    return " ".join(parts)


def _compute(db: Session, detection: Detection) -> Explanation:
    if detection.stage1_model_id is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "detection has no Stage 1 model recorded")
    model_row = db.query(MlModel).filter(MlModel.id == detection.stage1_model_id).first()
    if model_row is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "the Stage 1 model for this detection is no longer registered")

    flow_feature = db.query(FlowFeature).filter(FlowFeature.flow_id == detection.flow_id).first()
    if flow_feature is None:
        raise HTTPException(status.HTTP_409_CONFLICT, "the feature vector for this detection was not stored")

    features = inference_service.get_expected_features(flow_feature.feature_set_version)
    raw = np.asarray(flow_feature.feature_vector, dtype=float)
    scaler = inference_service.load_scaler(model_row.scaler_path)
    scaled = scaler.transform(raw.reshape(1, -1))

    model = inference_service.load_model(model_row.artifact_path)
    class_index = int(np.where(model.classes_ == 1)[0][0])
    explainer = _get_explainer(model_row.artifact_path)
    contributions, base_value = _malicious_class_slice(
        explainer.shap_values(scaled), explainer.expected_value, class_index
    )

    order = np.argsort(np.abs(contributions))[::-1][:TOP_N]
    ranked = [
        {
            "feature": features[i].strip(),
            # The raw value is what an analyst recognises; the scaled one is what
            # the model actually saw, so both are worth keeping.
            "value": float(raw[i]),
            "scaled_value": float(scaled[0][i]),
            "contribution": float(contributions[i]),
        }
        for i in order
    ]

    explanation = Explanation(
        detection_id=detection.id,
        method="SHAP",
        base_value=base_value,
        top_features=ranked,
        narrative=_narrative(
            probability=float(detection.stage1_probability or 0.0),
            verdict=detection.final_verdict,
            ranked=ranked,
        ),
    )
    db.add(explanation)
    db.commit()
    db.refresh(explanation)
    return explanation


def get_or_create(db: Session, detection_id: int) -> Explanation:
    detection = db.query(Detection).filter(Detection.id == detection_id).first()
    if detection is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "detection not found")

    existing = db.query(Explanation).filter(Explanation.detection_id == detection_id).first()
    if existing is not None:
        return existing
    return _compute(db, detection)


def get(db: Session, detection_id: int) -> Explanation | None:
    return db.query(Explanation).filter(Explanation.detection_id == detection_id).first()
