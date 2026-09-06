"""Generates and stores security reports (doc §13).

A report is a frozen snapshot: the summary is computed once, over an explicit
time window, and stored. Re-opening it later shows what the system knew when it
was generated, which is the whole point for an incident or compliance record —
recomputing on read would quietly rewrite history as alerts get resolved.

Every report is a window plus a set of filters. The type decides how the window
is worked out and what extra context is worth attaching:

    daily / weekly          the last 24 h / 7 days, whole estate
    patient                 one patient: who they are, which devices they were
                            on, and everything those devices reported
    device                  one device
    incident / compliance   an explicit window the operator chooses
    custom                  anything, any filters
"""

from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy import func
from sqlalchemy.orm import Session, joinedload

from models.alert import Alert
from models.attack_type import AttackType
from models.detection import Detection
from models.device import Device
from models.patient import Patient
from models.patient_device_assignment import PatientDeviceAssignment
from models.report import Report
from models.user import User
from models.vital_reading import VitalReading
from models.ward import Ward

PERIOD_BY_TYPE = {
    "daily": timedelta(days=1),
    "weekly": timedelta(days=7),
}

# A patient or device report is about a subject, not a period, so it defaults to
# a month rather than refusing — the operator can still narrow it.
DEFAULT_SUBJECT_PERIOD = timedelta(days=30)

REQUIRES_PATIENT = {"patient"}
REQUIRES_DEVICE = {"device"}
REQUIRES_WARD = {"ward"}


def _resolve_period(report_type: str, period_start: datetime | None,
                    period_end: datetime | None) -> tuple[datetime, datetime]:
    end = period_end or datetime.utcnow()
    if period_start is not None:
        if period_start >= end:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "period_start must be before period_end")
        return period_start, end
    span = PERIOD_BY_TYPE.get(report_type)
    if span is None and report_type in (REQUIRES_PATIENT | REQUIRES_DEVICE | REQUIRES_WARD):
        span = DEFAULT_SUBJECT_PERIOD
    if span is None:
        article = "an" if report_type[0] in "aeiou" else "a"
        raise HTTPException(
            status.HTTP_400_BAD_REQUEST,
            f"{article} '{report_type}' report needs an explicit period_start",
        )
    return end - span, end


def _patient_device_ids(db: Session, patient_id: int, start: datetime, end: datetime) -> list[int]:
    """Devices this patient was on at any point inside the window.

    An assignment counts if it overlaps the window at all — a device released
    halfway through still reported for them, and its alerts belong in the report.
    """
    rows = (
        db.query(PatientDeviceAssignment.device_id)
        .filter(
            PatientDeviceAssignment.patient_id == patient_id,
            PatientDeviceAssignment.assigned_at < end,
            (PatientDeviceAssignment.released_at.is_(None))
            | (PatientDeviceAssignment.released_at > start),
        )
        .distinct()
        .all()
    )
    return [r[0] for r in rows]


def _resolve_scope(db: Session, *, report_type: str, filters: dict,
                   start: datetime, end: datetime) -> tuple[list[int] | None, dict]:
    """Returns (device ids to restrict to, context to store with the summary).

    None means "the whole estate"; an empty list means the subject exists but had
    no devices in this window — a real answer, and not the same as no filter.
    """
    context: dict = {}

    if report_type in REQUIRES_PATIENT or filters.get("patient_id") is not None:
        patient_id = filters.get("patient_id")
        if patient_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "a patient report needs a patient_id")
        patient = (
            db.query(Patient).options(joinedload(Patient.ward))
            .filter(Patient.id == patient_id).first()
        )
        if patient is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown patient_id {patient_id}")

        device_ids = _patient_device_ids(db, patient.id, start, end)
        devices = db.query(Device).filter(Device.id.in_(device_ids)).all() if device_ids else []
        context["patient"] = {
            "id": patient.id,
            "patient_code": patient.patient_code,
            "age_band": patient.age_band,
            "sex": patient.sex,
            "ward": patient.ward.name if patient.ward else None,
            "admitted_at": patient.admitted_at.isoformat() if patient.admitted_at else None,
            "discharged_at": patient.discharged_at.isoformat() if patient.discharged_at else None,
            "devices": [
                {
                    "id": d.id,
                    "device_uid": d.device_uid,
                    "type": d.device_type.type_name if d.device_type else None,
                    "life_critical": bool(d.device_type and d.device_type.is_life_critical),
                }
                for d in devices
            ],
        }
        return device_ids, context

    if report_type in REQUIRES_DEVICE or filters.get("device_id") is not None:
        device_id = filters.get("device_id")
        if device_id is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "a device report needs a device_id")
        device = db.query(Device).filter(Device.id == device_id).first()
        if device is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown device_id {device_id}")
        context["device"] = {
            "id": device.id,
            "device_uid": device.device_uid,
            "type": device.device_type.type_name if device.device_type else None,
            "ward": device.ward.name if device.ward else None,
            "status": device.status,
        }
        return [device.id], context

    if report_type in REQUIRES_WARD or filters.get("ward"):
        if not filters.get("ward"):
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "a ward report needs a ward name")
        ward = db.query(Ward).filter(Ward.name == filters["ward"]).first()
        if ward is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown ward '{filters['ward']}'")
        ids = [d.id for d in db.query(Device.id).filter(Device.ward_id == ward.id).all()]
        context["ward"] = {"name": ward.name, "criticality": ward.criticality, "devices": len(ids)}
        return ids, context

    return None, context


def _scoped(query, column, device_ids: list[int] | None):
    if device_ids is None:
        return query
    if not device_ids:
        # Nothing in scope: match no rows rather than silently widening to all.
        return query.filter(column.is_(None), column.isnot(None))
    return query.filter(column.in_(device_ids))


def _summarise(db: Session, *, start: datetime, end: datetime, device_ids: list[int] | None,
               filters: dict) -> dict:
    detections = _scoped(
        db.query(Detection).filter(Detection.detected_at >= start, Detection.detected_at < end),
        Detection.device_id, device_ids,
    )
    alerts = _scoped(
        db.query(Alert).filter(Alert.first_seen_at >= start, Alert.first_seen_at < end),
        Alert.device_id, device_ids,
    )
    if filters.get("severity"):
        alerts = alerts.filter(Alert.severity == filters["severity"])
        detections = detections.filter(Detection.severity == filters["severity"])
    if filters.get("verdict"):
        detections = detections.filter(Detection.final_verdict == filters["verdict"])

    verdicts = dict(
        detections.with_entities(Detection.final_verdict, func.count(Detection.id))
        .group_by(Detection.final_verdict).all()
    )
    severities = dict(
        alerts.with_entities(Alert.severity, func.count(Alert.id)).group_by(Alert.severity).all()
    )
    statuses = dict(
        alerts.with_entities(Alert.status, func.count(Alert.id)).group_by(Alert.status).all()
    )

    total_detections = sum(verdicts.values())
    families = (
        alerts.join(AttackType, Alert.attack_type_id == AttackType.id)
        .with_entities(AttackType.display_name, func.count(Alert.id))
        .group_by(AttackType.display_name)
        .order_by(func.count(Alert.id).desc())
        .all()
    )
    busiest = (
        detections.join(Device, Detection.device_id == Device.id)
        .with_entities(Device.device_uid, func.count(Detection.id))
        .group_by(Device.device_uid)
        .order_by(func.count(Detection.id).desc())
        .limit(10)
        .all()
    )
    avg_latency = detections.with_entities(func.avg(Detection.inference_latency_ms)).scalar()

    vitals = _scoped(
        db.query(VitalReading).filter(
            VitalReading.recorded_at >= start, VitalReading.recorded_at < end
        ),
        VitalReading.device_id, device_ids,
    )
    vitals_total = vitals.count()
    vitals_scored = vitals.filter(VitalReading.residual_zscore.isnot(None)).count()
    vitals_flagged = vitals.filter(VitalReading.injection_suspected.is_(True)).count()

    malicious = total_detections - verdicts.get("benign", 0)
    return {
        "total_detections": total_detections,
        "detections_by_verdict": verdicts,
        "flagged_share": round(malicious / total_detections, 4) if total_detections else 0.0,
        "total_alerts": sum(severities.values()),
        "alerts_by_severity": severities,
        "alerts_by_status": statuses,
        "top_attack_families": [{"family": f, "alerts": c} for f, c in families],
        "busiest_devices": [{"device_uid": d, "detections": c} for d, c in busiest],
        "avg_inference_latency_ms": round(float(avg_latency), 3) if avg_latency is not None else None,
        "vitals_readings": vitals_total,
        "vitals_scored_by_stage4": vitals_scored,
        "vitals_implausible": vitals_flagged,
    }


def _default_title(report_type: str, start: datetime, end: datetime, context: dict) -> str:
    if "patient" in context:
        return f"Patient report — {context['patient']['patient_code']}, {start:%d %b} to {end:%d %b %Y}"
    if "device" in context:
        return f"Device report — {context['device']['device_uid']}, {start:%d %b} to {end:%d %b %Y}"
    if "ward" in context:
        return f"Ward report — {context['ward']['name']}, {start:%d %b} to {end:%d %b %Y}"
    label = report_type.capitalize()
    if start.date() == (end - timedelta(microseconds=1)).date():
        return f"{label} security report — {start:%d %b %Y}"
    return f"{label} security report — {start:%d %b %Y} to {end:%d %b %Y}"


def generate(db: Session, *, report_type: str, title: str | None, period_start: datetime | None,
             period_end: datetime | None, filters: dict, actor_user_id: int) -> Report:
    filters = {k: v for k, v in (filters or {}).items() if v not in (None, "")}
    start, end = _resolve_period(report_type, period_start, period_end)
    device_ids, context = _resolve_scope(
        db, report_type=report_type, filters=filters, start=start, end=end
    )
    summary = _summarise(db, start=start, end=end, device_ids=device_ids, filters=filters)
    summary["scope"] = context
    # Kept so the export can reproduce the same scope without re-resolving the
    # patient's assignments, which may have changed since.
    summary["device_ids"] = device_ids

    report = Report(
        report_type=report_type,
        title=title or _default_title(report_type, start, end, context),
        period_start=start,
        period_end=end,
        filters=filters,
        summary_stats=summary,
        generated_by=actor_user_id,
    )
    db.add(report)
    db.commit()
    db.refresh(report)
    return report


def list_reports(db: Session, *, page: int, size: int, report_type: str | None = None,
                 generated_by: int | None = None, patient_id: int | None = None,
                 created_from: datetime | None = None, created_to: datetime | None = None):
    """Every report, whoever generated it.

    Reports summarise the estate rather than one person's work, so there is no
    per-author scoping: anyone holding reports.read sees the lot. These filter
    arguments are choices the caller makes, not restrictions imposed on them.
    """
    query = db.query(Report)
    if report_type:
        query = query.filter(Report.report_type == report_type)
    if generated_by is not None:
        query = query.filter(Report.generated_by == generated_by)
    if patient_id is not None:
        # filters is a JSON column; extracting the key is an exact match, unlike
        # a LIKE over the serialised blob.
        query = query.filter(func.json_extract(Report.filters, "$.patient_id") == patient_id)
    if created_from is not None:
        query = query.filter(Report.created_at >= created_from)
    if created_to is not None:
        query = query.filter(Report.created_at < created_to)

    query = query.order_by(Report.created_at.desc(), Report.id.desc())
    total = query.count()
    items = query.options(joinedload(Report.author)).offset((page - 1) * size).limit(size).all()
    return items, total


def list_authors(db: Session) -> list[dict]:
    """Who has generated reports, and how many — for the author filter."""
    rows = (
        db.query(User.id, User.username, func.count(Report.id))
        .join(Report, Report.generated_by == User.id)
        .group_by(User.id, User.username)
        .order_by(func.count(Report.id).desc())
        .all()
    )
    return [{"id": uid, "username": name, "reports": count} for uid, name, count in rows]


def get_report(db: Session, report_id: int) -> Report | None:
    return db.query(Report).options(joinedload(Report.author)).filter(Report.id == report_id).first()


def delete_report(db: Session, *, report_id: int) -> None:
    report = get_report(db, report_id)
    if report is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "report not found")
    db.delete(report)
    db.commit()


# A spreadsheet nobody can open is worse than a truncated one; this caps each
# detail sheet so a month-long estate-wide report can't try to write a million
# rows into memory.
MAX_EXPORT_ROWS = 5000


def detail_rows(db: Session, report: Report) -> dict[str, list[dict]]:
    """The individual records behind a report's numbers, for the export.

    Re-queried from the report's own window and scope rather than stored: the
    window is closed, so these are the same rows, but an alert's *status* may
    have moved on since it was generated. The Summary sheet shows the frozen
    figures; the detail sheets are labelled as current.
    """
    summary = report.summary_stats or {}
    device_ids = summary.get("device_ids")
    filters = report.filters or {}
    start, end = report.period_start, report.period_end

    alerts_q = _scoped(
        db.query(Alert)
        .options(joinedload(Alert.device), joinedload(Alert.attack_type), joinedload(Alert.assignee))
        .filter(Alert.first_seen_at >= start, Alert.first_seen_at < end),
        Alert.device_id, device_ids,
    ).order_by(Alert.risk_score.desc())
    if filters.get("severity"):
        alerts_q = alerts_q.filter(Alert.severity == filters["severity"])

    detections_q = _scoped(
        db.query(Detection)
        .options(joinedload(Detection.device), joinedload(Detection.stage2_attack_type))
        .filter(Detection.detected_at >= start, Detection.detected_at < end),
        Detection.device_id, device_ids,
    ).order_by(Detection.detected_at.desc())
    if filters.get("verdict"):
        detections_q = detections_q.filter(Detection.final_verdict == filters["verdict"])
    if filters.get("severity"):
        detections_q = detections_q.filter(Detection.severity == filters["severity"])

    vitals_q = _scoped(
        db.query(VitalReading)
        .options(joinedload(VitalReading.device))
        .filter(VitalReading.recorded_at >= start, VitalReading.recorded_at < end),
        VitalReading.device_id, device_ids,
    ).order_by(VitalReading.recorded_at.desc())

    return {
        "Alerts": [
            {
                "Alert ID": a.alert_uid,
                "Raised": a.first_seen_at,
                "Device": a.device.device_uid if a.device else None,
                "Attack family": a.attack_type.display_name if a.attack_type else None,
                "Severity": a.severity,
                "Risk score": float(a.risk_score) if a.risk_score is not None else None,
                "Status": a.status,
                "Assigned to": a.assignee.username if a.assignee else None,
                "Occurrences": a.occurrence_count,
                "Title": a.title,
            }
            for a in alerts_q.limit(MAX_EXPORT_ROWS).all()
        ],
        "Detections": [
            {
                "Detection ID": d.id,
                "Detected": d.detected_at,
                "Device": d.device.device_uid if d.device else None,
                "Stage 1 label": d.stage1_label,
                "Stage 1 probability": float(d.stage1_probability) if d.stage1_probability is not None else None,
                "Stage 2 family": d.stage2_attack_type.display_name if d.stage2_attack_type else None,
                "Stage 3 anomaly": bool(d.stage3_is_anomaly),
                "Stage 4 injection": bool(d.stage4_injection_suspected),
                "Stage 4 z-score": float(d.stage4_max_zscore) if d.stage4_max_zscore is not None else None,
                "Verdict": d.final_verdict,
                "Severity": d.severity,
                "Latency (ms)": float(d.inference_latency_ms) if d.inference_latency_ms is not None else None,
            }
            for d in detections_q.limit(MAX_EXPORT_ROWS).all()
        ],
        "Vitals": [
            {
                "Recorded": v.recorded_at,
                "Device": v.device.device_uid if v.device else None,
                "Heart rate": v.heart_rate,
                "SpO2": v.spo2,
                "Systolic": v.systolic_bp,
                "Diastolic": v.diastolic_bp,
                "Temperature": float(v.body_temp) if v.body_temp is not None else None,
                "Respiration": v.respiration_rate,
                "Stage 4 z-score": float(v.residual_zscore) if v.residual_zscore is not None else None,
                "Implausible": bool(v.injection_suspected),
            }
            for v in vitals_q.limit(MAX_EXPORT_ROWS).all()
        ],
    }
