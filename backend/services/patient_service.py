import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.device import Device
from models.patient import Patient
from models.patient_device_assignment import PatientDeviceAssignment
from models.ward import Ward


def _resolve_ward(db: Session, ward_name: str | None) -> Ward | None:
    if ward_name is None:
        return None
    ward = db.query(Ward).filter(Ward.name == ward_name).first()
    if ward is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown ward '{ward_name}'")
    return ward


def list_patients(db: Session, *, page: int, size: int, ward: str | None = None,
                   include_discharged: bool = False):
    query = db.query(Patient)
    if ward:
        query = query.join(Ward).filter(Ward.name == ward)
    if not include_discharged:
        query = query.filter(Patient.discharged_at.is_(None))
    query = query.order_by(Patient.id)
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total


def get_patient(db: Session, patient_id: int) -> Patient | None:
    return db.query(Patient).filter(Patient.id == patient_id).first()


def create_patient(db: Session, *, age_band, sex, ward_name, baseline_hr_min, baseline_hr_max,
                    baseline_spo2_min, notes) -> Patient:
    """patient_code (PT-0001 style pseudonym) is server-assigned, never client input.

    The row is inserted with a temporary unique placeholder so we can learn the
    autoincrement id, then relabelled — avoids a race on a hand-rolled counter.
    """
    ward = _resolve_ward(db, ward_name)
    patient = Patient(
        patient_code=f"TMP-{uuid.uuid4().hex[:12]}",
        age_band=age_band,
        sex=sex,
        ward_id=ward.id if ward else None,
        admitted_at=datetime.utcnow(),
        baseline_hr_min=baseline_hr_min,
        baseline_hr_max=baseline_hr_max,
        baseline_spo2_min=baseline_spo2_min,
        notes=notes,
    )
    db.add(patient)
    db.commit()
    db.refresh(patient)

    patient.patient_code = f"PT-{patient.id:04d}"
    db.commit()
    db.refresh(patient)
    return patient


def update_patient(db: Session, *, patient_id: int, updates: dict) -> Patient:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient not found")

    if "ward" in updates:
        ward = _resolve_ward(db, updates["ward"])
        patient.ward_id = ward.id if ward else None

    if "discharged" in updates:
        patient.discharged_at = datetime.utcnow() if updates["discharged"] else None

    for field in ("age_band", "sex", "baseline_hr_min", "baseline_hr_max", "baseline_spo2_min", "notes"):
        if field in updates:
            setattr(patient, field, updates[field])

    db.commit()
    db.refresh(patient)
    return patient


def list_assignments(db: Session, patient_id: int) -> list[PatientDeviceAssignment]:
    return (
        db.query(PatientDeviceAssignment)
        .filter(PatientDeviceAssignment.patient_id == patient_id)
        .order_by(PatientDeviceAssignment.assigned_at.desc())
        .all()
    )


def assign_device(db: Session, *, patient_id: int, device_id: int) -> PatientDeviceAssignment:
    patient = db.query(Patient).filter(Patient.id == patient_id).first()
    if patient is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "patient not found")

    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown device_id")

    active = (
        db.query(PatientDeviceAssignment)
        .filter(
            PatientDeviceAssignment.device_id == device_id,
            PatientDeviceAssignment.released_at.is_(None),
        )
        .first()
    )
    if active is not None:
        raise HTTPException(
            status.HTTP_409_CONFLICT, "device is already assigned to a patient — release it first"
        )

    assignment = PatientDeviceAssignment(
        patient_id=patient_id, device_id=device_id, assigned_at=datetime.utcnow()
    )
    db.add(assignment)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "could not create assignment")
    db.refresh(assignment)
    return assignment


def release_assignment(db: Session, *, patient_id: int, assignment_id: int) -> PatientDeviceAssignment:
    assignment = (
        db.query(PatientDeviceAssignment)
        .filter(
            PatientDeviceAssignment.id == assignment_id,
            PatientDeviceAssignment.patient_id == patient_id,
        )
        .first()
    )
    if assignment is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "assignment not found")
    if assignment.released_at is not None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "assignment already released")

    assignment.released_at = datetime.utcnow()
    db.commit()
    db.refresh(assignment)
    return assignment
