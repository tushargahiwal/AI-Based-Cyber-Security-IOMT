from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.device import WardOut
from schemas.patient import (
    AssignmentCreateRequest,
    AssignmentOut,
    PatientCreateRequest,
    PatientListResponse,
    PatientOut,
    PatientUpdateRequest,
)
from services import audit_service, patient_service

router = APIRouter(prefix="/api/v1/patients", tags=["patients"])


def _to_patient_out(p) -> PatientOut:
    return PatientOut(
        id=p.id,
        patient_code=p.patient_code,
        age_band=p.age_band,
        sex=p.sex,
        ward=WardOut.model_validate(p.ward) if p.ward else None,
        admitted_at=p.admitted_at,
        discharged_at=p.discharged_at,
        baseline_hr_min=p.baseline_hr_min,
        baseline_hr_max=p.baseline_hr_max,
        baseline_spo2_min=p.baseline_spo2_min,
        notes=p.notes,
    )


def _to_assignment_out(a) -> AssignmentOut:
    return AssignmentOut(
        id=a.id,
        patient_id=a.patient_id,
        device_id=a.device_id,
        device_uid=a.device.device_uid if a.device else None,
        assigned_at=a.assigned_at,
        released_at=a.released_at,
    )


@router.get("", response_model=PatientListResponse)
def list_patients(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    ward: str | None = Query(default=None),
    include_discharged: bool = Query(False),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("patients.read")),
):
    items, total = patient_service.list_patients(
        db, page=page, size=size, ward=ward, include_discharged=include_discharged
    )
    return PatientListResponse(items=[_to_patient_out(p) for p in items], total=total, page=page, size=size)


@router.post("", response_model=PatientOut, status_code=status.HTTP_201_CREATED)
def create_patient(
    body: PatientCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("patients.write")),
):
    patient = patient_service.create_patient(
        db,
        age_band=body.age_band,
        sex=body.sex,
        ward_name=body.ward,
        baseline_hr_min=body.baseline_hr_min,
        baseline_hr_max=body.baseline_hr_max,
        baseline_spo2_min=body.baseline_spo2_min,
        notes=body.notes,
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="CREATE_PATIENT",
        entity_type="patients",
        entity_id=patient.id,
        new_value={"patient_code": patient.patient_code},
        ip_address=request.client.host if request.client else None,
    )
    return _to_patient_out(patient)


@router.get("/{patient_id}", response_model=PatientOut)
def get_patient(
    patient_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("patients.read")),
):
    patient = patient_service.get_patient(db, patient_id)
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient not found")
    return _to_patient_out(patient)


@router.patch("/{patient_id}", response_model=PatientOut)
def update_patient(
    patient_id: int,
    body: PatientUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("patients.write")),
):
    updates = body.model_dump(exclude_unset=True)
    patient = patient_service.update_patient(db, patient_id=patient_id, updates=updates)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="DISCHARGE_PATIENT" if "discharged" in updates else "UPDATE_PATIENT",
        entity_type="patients",
        entity_id=patient_id,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return _to_patient_out(patient)


@router.get("/{patient_id}/assignments", response_model=list[AssignmentOut])
def list_assignments(
    patient_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("patients.read")),
):
    return [_to_assignment_out(a) for a in patient_service.list_assignments(db, patient_id)]


@router.post("/{patient_id}/assignments", response_model=AssignmentOut, status_code=status.HTTP_201_CREATED)
def assign_device(
    patient_id: int,
    body: AssignmentCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("patients.write")),
):
    assignment = patient_service.assign_device(db, patient_id=patient_id, device_id=body.device_id)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="ASSIGN_DEVICE",
        entity_type="patient_device_assignments",
        entity_id=assignment.id,
        new_value={"patient_id": patient_id, "device_id": body.device_id},
        ip_address=request.client.host if request.client else None,
    )
    return _to_assignment_out(assignment)


@router.post("/{patient_id}/assignments/{assignment_id}/release", response_model=AssignmentOut)
def release_assignment(
    patient_id: int,
    assignment_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("patients.write")),
):
    assignment = patient_service.release_assignment(db, patient_id=patient_id, assignment_id=assignment_id)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="RELEASE_ASSIGNMENT",
        entity_type="patient_device_assignments",
        entity_id=assignment.id,
        ip_address=request.client.host if request.client else None,
    )
    return _to_assignment_out(assignment)
