from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.vital import VitalIngestRequest, VitalListResponse, VitalOut
from services import vitals_service

router = APIRouter(prefix="/api/v1/vitals", tags=["vitals"])


def _to_out(v) -> VitalOut:
    return VitalOut(
        id=v.id,
        device_id=v.device_id,
        patient_id=v.patient_id,
        recorded_at=v.recorded_at,
        heart_rate=v.heart_rate,
        spo2=v.spo2,
        systolic_bp=v.systolic_bp,
        diastolic_bp=v.diastolic_bp,
        body_temp=float(v.body_temp) if v.body_temp is not None else None,
        respiration_rate=v.respiration_rate,
        is_plausible=v.is_plausible,
        predicted_values=v.predicted_values,
        residual_zscore=float(v.residual_zscore) if v.residual_zscore is not None else None,
        injection_suspected=v.injection_suspected,
        stage4_evaluated=v.residual_zscore is not None,
    )


@router.post("", response_model=VitalOut, status_code=status.HTTP_201_CREATED)
def ingest_vital(
    body: VitalIngestRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("vitals.write")),
):
    reading = vitals_service.ingest_reading(db, data=body.model_dump(exclude_none=True))
    return _to_out(reading)


@router.get("", response_model=VitalListResponse)
def list_vitals(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=500),
    device_id: int | None = Query(default=None),
    patient_id: int | None = Query(default=None),
    injection_only: bool = Query(default=False),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("vitals.read")),
):
    items, total = vitals_service.list_readings(
        db, page=page, size=size, device_id=device_id,
        patient_id=patient_id, injection_only=injection_only,
    )
    return VitalListResponse(items=[_to_out(v) for v in items], total=total, page=page, size=size)


@router.get("/{reading_id}", response_model=VitalOut)
def get_vital(
    reading_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("vitals.read")),
):
    reading = vitals_service.get_reading(db, reading_id)
    if reading is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "vital reading not found")
    return _to_out(reading)
