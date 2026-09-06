import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.attack_type import AttackType
from models.detection import Detection
from models.flow_feature import FlowFeature
from models.ml_model import MlModel
from models.network_flow import NetworkFlow
from services import alert_service, inference_service, vitals_service
from services.broadcast import broadcaster

# Stage 2 predicts a dataset-native family name; map it to the attack_types.code
# seeded for this dataset (see ml/train_multiclass.py docstring for why WUSTL
# only has these two, not the full CICIoMT2024 six-family taxonomy).
STAGE2_FAMILY_TO_CODE = {
    "Data Alteration": "DATA_ALTERATION",
    "Spoofing": "SPOOFING_MITM",
}


def _resolve_active_model(db: Session, stage: int) -> MlModel | None:
    return db.query(MlModel).filter(MlModel.stage == stage, MlModel.is_active.is_(True)).first()


def _resolve_active_stage1_model(db: Session) -> MlModel:
    model = _resolve_active_model(db, 1)
    if model is None:
        raise HTTPException(status.HTTP_503_SERVICE_UNAVAILABLE, "no active Stage 1 model registered")
    return model


def submit_detection(
    db: Session,
    *,
    flow_uid: str | None,
    device_id: int | None,
    feature_vector: list[float],
    feature_set_version: str,
    src_ip: str,
    dst_ip: str,
    protocol: str,
    capture_source: str,
) -> dict:
    stage1_model = _resolve_active_stage1_model(db)

    try:
        expected = inference_service.get_expected_features(feature_set_version)
    except ValueError as exc:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, str(exc))
    if len(feature_vector) != len(expected):
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"feature_vector has {len(feature_vector)} values, expected {len(expected)} for '{feature_set_version}'",
        )

    start = datetime.utcnow()
    stage1 = inference_service.run_stage1(
        artifact_path=stage1_model.artifact_path,
        scaler_path=stage1_model.scaler_path,
        feature_vector=feature_vector,
    )

    stage2 = None
    stage2_model = None
    if stage1["label"] == "malicious":
        stage2_model = _resolve_active_model(db, 2)
        if stage2_model is not None and stage2_model.output_classes:
            stage2 = inference_service.run_stage2(
                artifact_path=stage2_model.artifact_path,
                scaler_path=stage2_model.scaler_path,
                feature_vector=feature_vector,
                output_classes=stage2_model.output_classes,
            )

    # Stage 3 runs on every flow, benign or not — that's the whole point of an
    # unsupervised anomaly check (doc §8.5): it can flag what Stage 1 missed.
    stage3 = None
    stage3_model = _resolve_active_model(db, 3)
    if stage3_model is not None and stage3_model.threshold is not None:
        stage3 = inference_service.run_stage3(
            artifact_path=stage3_model.artifact_path,
            scaler_path=stage3_model.scaler_path,
            feature_vector=feature_vector,
            threshold=float(stage3_model.threshold),
        )

    # Stage 4 runs on the vitals stream at ingest (it needs a 30-reading window
    # this flow doesn't carry), so here we only correlate: does this device have
    # a recent reading the LSTM already judged implausible? See vitals_service.
    stage4_reading = vitals_service.get_stage4_status(db, device_id, at=start)
    stage4 = None
    if stage4_reading is not None:
        meta = stage4_reading.predicted_values or {}
        stage4 = {
            "reading_id": stage4_reading.id,
            "max_zscore": float(stage4_reading.residual_zscore),
            "threshold": float(meta.get("threshold", vitals_service.DEFAULT_ZSCORE_THRESHOLD)),
            "worst_vital": meta.get("worst_vital"),
            "injection_suspected": stage4_reading.injection_suspected,
        }

    latency_ms = (datetime.utcnow() - start).total_seconds() * 1000

    now = datetime.utcnow()
    flow = NetworkFlow(
        flow_uid=flow_uid or str(uuid.uuid4()),
        device_id=device_id,
        src_ip=src_ip,
        dst_ip=dst_ip,
        protocol=protocol,
        flow_start=now,
        flow_end=now,
        capture_source=capture_source,
    )
    db.add(flow)
    db.flush()  # assigns flow.id without ending the transaction

    db.add(FlowFeature(flow_id=flow.id, feature_vector=feature_vector, feature_set_version=feature_set_version))

    attack_type = None
    if stage2 is not None:
        code = STAGE2_FAMILY_TO_CODE.get(stage2["family"])
        if code is not None:
            attack_type = db.query(AttackType).filter(AttackType.code == code).first()

    final_verdict, severity = _decide(
        stage1_probability=stage1["probability"],
        stage2=stage2,
        stage2_threshold=float(stage2_model.threshold) if stage2_model and stage2_model.threshold else 0.6,
        attack_type=attack_type,
        stage3=stage3,
        stage4=stage4,
    )
    if final_verdict == "data_integrity" and stage4 is not None:
        # How far past the flagging threshold the worst vital landed, saturating
        # at 2x — beyond that it is simply "very implausible", not more certain.
        final_confidence = min(0.99, stage4["max_zscore"] / (2 * stage4["threshold"]))
    elif stage2 is not None and attack_type is not None:
        final_confidence = stage2["confidence"]
    else:
        final_confidence = (
            stage1["probability"] if stage1["label"] == "malicious" else 1 - stage1["probability"]
        )

    detection = Detection(
        flow_id=flow.id,
        device_id=device_id,
        stage1_model_id=stage1_model.id,
        stage1_label=stage1["label"],
        stage1_probability=stage1["probability"],
        stage2_model_id=stage2_model.id if stage2 is not None else None,
        stage2_attack_type_id=attack_type.id if attack_type is not None else None,
        stage2_confidence=stage2["confidence"] if stage2 is not None else None,
        stage2_class_probs=stage2["class_probabilities"] if stage2 is not None else None,
        stage3_model_id=stage3_model.id if stage3 is not None else None,
        stage3_reconstruction_error=stage3["reconstruction_error"] if stage3 is not None else None,
        stage3_anomaly_score=stage3["anomaly_score"] if stage3 is not None else None,
        stage3_is_anomaly=stage3["is_anomaly"] if stage3 is not None else False,
        stage4_injection_suspected=stage4["injection_suspected"] if stage4 is not None else False,
        stage4_max_zscore=stage4["max_zscore"] if stage4 is not None else None,
        final_verdict=final_verdict,
        final_confidence=final_confidence,
        severity=severity,
        inference_latency_ms=latency_ms,
        detected_at=now,
    )
    db.add(detection)
    db.commit()
    db.refresh(detection)
    db.refresh(flow)

    alert = alert_service.maybe_create_alert(db, detection=detection)

    # The live monitor shows every verdict, not just the alert-worthy ones —
    # a wall of benign traffic is what makes the occasional attack visible.
    broadcaster.publish({
        "type": "detection",
        "data": {
            "detection_id": detection.id,
            "device_id": device_id,
            "src_ip": src_ip,
            "dst_ip": dst_ip,
            "protocol": protocol,
            "stage1_label": stage1["label"],
            "stage1_probability": stage1["probability"],
            "stage3_is_anomaly": bool(stage3 and stage3["is_anomaly"]),
            "stage4_injection_suspected": bool(stage4 and stage4["injection_suspected"]),
            "final_verdict": final_verdict,
            "severity": severity,
            "alert_uid": alert.alert_uid if alert else None,
            "detected_at": now.isoformat(),
        },
    })

    return {
        "detection": detection,
        "flow": flow,
        "stage1": stage1,
        "stage2": stage2,
        "stage3": stage3,
        "stage4": stage4,
        "attack_type": attack_type,
        "alert": alert,
    }


def _decide(*, stage1_probability: float, stage2: dict | None, stage2_threshold: float,
            attack_type, stage3: dict | None, stage4: dict | None = None) -> tuple[str, str]:
    """The doc §14.1 decision table across all four stages."""
    stage3_anomaly = stage3 is not None and stage3["is_anomaly"]
    stage4_injection = stage4 is not None and stage4["injection_suspected"]

    # Stage 4 owns the 'data_integrity' verdict: the vitals this device reported
    # don't follow from its own recent history, so the readings themselves are
    # suspect regardless of what the traffic looks like.
    if stage4_injection:
        if stage1_probability > 0.65:
            # Traffic says attack AND the vitals are implausible — two independent
            # signals agreeing is the strongest case there is.
            severity = (attack_type.default_severity if attack_type is not None else None) or "high"
            return "data_integrity", severity
        if stage1_probability >= 0.35 or stage3_anomaly:
            return "data_integrity", "medium"
        # Clean traffic, plausible flow — the vitals are the only evidence. At
        # z>3 the forecaster flags ~6.8% of benign windows
        # (models/vitals_lstm_results.json), and a genuinely deteriorating
        # patient looks the same, so this is a "have a clinician look" signal.
        return "data_integrity", "low"

    if 0.35 <= stage1_probability <= 0.65:
        return ("zero_day_suspect", "medium") if stage3_anomaly else ("uncertain", "low")

    if stage1_probability < 0.35:
        return ("zero_day_suspect", "medium") if stage3_anomaly else ("benign", "info")

    # malicious per Stage 1 (probability > 0.65)
    if stage2 is not None and attack_type is not None and stage2["confidence"] >= stage2_threshold:
        return "known_attack", attack_type.default_severity or "medium"

    # Stage 1 malicious but Stage 2 couldn't confidently name a family
    if stage3_anomaly:
        return "zero_day_suspect", "high"
    return "uncertain", "medium"


def list_detections(db: Session, *, page: int, size: int, final_verdict: str | None = None,
                     device_id: int | None = None):
    query = db.query(Detection)
    if final_verdict:
        query = query.filter(Detection.final_verdict == final_verdict)
    if device_id is not None:
        query = query.filter(Detection.device_id == device_id)
    query = query.order_by(Detection.detected_at.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total


def get_detection(db: Session, detection_id: int) -> Detection | None:
    return db.query(Detection).filter(Detection.id == detection_id).first()
