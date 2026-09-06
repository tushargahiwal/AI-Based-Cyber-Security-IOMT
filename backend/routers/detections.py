from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.detection import (
    DetectRequest,
    DetectResponse,
    DetectionListResponse,
    DetectionOut,
    Stage1Out,
    Stage2Out,
    ExplanationOut,
    Stage3Out,
    Stage4Out,
)
from services import detection_service, explanation_service

router = APIRouter(prefix="/api/v1", tags=["detections"])


def _to_out(d) -> DetectionOut:
    return DetectionOut(
        id=d.id,
        flow_id=d.flow_id,
        device_id=d.device_id,
        stage1_label=d.stage1_label,
        stage1_probability=float(d.stage1_probability) if d.stage1_probability is not None else None,
        stage2_attack_family=d.stage2_attack_type.display_name if d.stage2_attack_type else None,
        stage2_confidence=float(d.stage2_confidence) if d.stage2_confidence is not None else None,
        stage3_anomaly_score=float(d.stage3_anomaly_score) if d.stage3_anomaly_score is not None else None,
        stage3_is_anomaly=d.stage3_is_anomaly,
        stage4_injection_suspected=d.stage4_injection_suspected,
        stage4_max_zscore=float(d.stage4_max_zscore) if d.stage4_max_zscore is not None else None,
        final_verdict=d.final_verdict,
        final_confidence=float(d.final_confidence) if d.final_confidence is not None else None,
        severity=d.severity,
        inference_latency_ms=float(d.inference_latency_ms) if d.inference_latency_ms is not None else None,
        detected_at=d.detected_at,
    )


@router.post("/detect", response_model=DetectResponse, status_code=status.HTTP_201_CREATED)
def detect(
    body: DetectRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    result = detection_service.submit_detection(
        db,
        flow_uid=body.flow_uid,
        device_id=body.device_id,
        feature_vector=body.feature_vector,
        feature_set_version=body.feature_set_version,
        src_ip=body.src_ip,
        dst_ip=body.dst_ip,
        protocol=body.protocol,
        capture_source=body.capture_source,
    )
    detection = result["detection"]
    flow = result["flow"]

    stage2_out = None
    if result["stage2"] is not None:
        attack_type = result["attack_type"]
        stage2_out = Stage2Out(
            attack_family=attack_type.display_name if attack_type else None,
            confidence=result["stage2"]["confidence"],
            class_probabilities=result["stage2"]["class_probabilities"],
        )

    stage3_out = Stage3Out(**result["stage3"]) if result["stage3"] is not None else None
    alert = result.get("alert")

    return DetectResponse(
        detection_id=detection.id,
        flow_id=flow.id,
        flow_uid=flow.flow_uid,
        final_verdict=detection.final_verdict,
        severity=detection.severity,
        final_confidence=float(detection.final_confidence),
        stage1=Stage1Out(**result["stage1"]),
        stage2=stage2_out,
        stage3=stage3_out,
        stage4=Stage4Out(**result["stage4"]) if result["stage4"] is not None else None,
        alert_id=alert.id if alert else None,
        alert_uid=alert.alert_uid if alert else None,
        inference_latency_ms=float(detection.inference_latency_ms),
        detected_at=detection.detected_at,
    )


@router.get("/detections", response_model=DetectionListResponse)
def list_detections(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    final_verdict: str | None = Query(default=None),
    device_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    items, total = detection_service.list_detections(
        db, page=page, size=size, final_verdict=final_verdict, device_id=device_id
    )
    return DetectionListResponse(items=[_to_out(d) for d in items], total=total, page=page, size=size)


@router.get("/detections/{detection_id}", response_model=DetectionOut)
def get_detection(
    detection_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    d = detection_service.get_detection(db, detection_id)
    if d is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "detection not found")
    return _to_out(d)


@router.post("/detections/{detection_id}/explain", response_model=ExplanationOut,
             status_code=status.HTTP_200_OK)
def explain_detection(
    detection_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("models.read")),
):
    """Why Stage 1 scored this flow the way it did.

    POST rather than GET because the first call computes and stores the
    explanation; every call after that returns the stored one unchanged.
    """
    explanation = explanation_service.get_or_create(db, detection_id)
    return ExplanationOut.model_validate(explanation, from_attributes=True)


@router.get("/detections/{detection_id}/explanation", response_model=ExplanationOut)
def get_detection_explanation(
    detection_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("models.read")),
):
    explanation = explanation_service.get(db, detection_id)
    if explanation is None:
        raise HTTPException(
            status.HTTP_404_NOT_FOUND,
            "no explanation stored for this detection yet — POST to /explain to generate one",
        )
    return ExplanationOut.model_validate(explanation, from_attributes=True)
