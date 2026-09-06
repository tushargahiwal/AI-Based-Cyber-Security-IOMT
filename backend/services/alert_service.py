"""Turns severity-worthy detections into deduplicated, actionable alerts —
doc Module 5 (§11) and the risk-score formula in §14.2.
"""

import uuid
from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.alert import Alert
from models.alert_action import AlertAction
from models.blocklist import BlocklistEntry
from models.device import Device
from models.mitigation_recommendation import MitigationRecommendation
from models.patient_device_assignment import PatientDeviceAssignment
from models.user import User
from services import notification_service

ALERT_SEVERITIES = {"medium", "high", "critical"}

# Action types that actually change system state when applied. Everything else
# ("notify_biomed", "manual_review", "force_reauth") is carried out by a person
# off-platform, so applying it only records that someone took it on.
# "rate_limit" sits with those: there is no rate limiter here to program yet.
ENFORCING_ACTIONS = {"isolate_source", "block_ip", "revoke_mqtt_client"}

SEVERITY_WEIGHT = {"info": 0.1, "low": 0.3, "medium": 0.55, "high": 0.8, "critical": 1.0}
WARD_CRITICALITY_WEIGHT = {"low": 0.25, "medium": 0.5, "high": 0.75, "critical": 1.0}


def _device_criticality(device: Device | None) -> float:
    if device is None:
        return 0.5
    if device.device_type and device.device_type.is_life_critical:
        return 1.0
    if device.ward:
        return WARD_CRITICALITY_WEIGHT.get(device.ward.criticality, 0.5)
    return 0.5


def _compute_risk_score(*, severity: str, final_confidence: float, device: Device | None,
                         stage3_anomaly_score: float | None, patient_at_risk: bool) -> float:
    """doc §14.2: 35% severity, 25% confidence, 20% device criticality, 10%
    anomaly score, 10% whether a patient is currently on this device."""
    anomaly_norm = min((stage3_anomaly_score or 0.0) / 3.0, 1.0)
    risk = 100 * (
        0.35 * SEVERITY_WEIGHT.get(severity, 0.5)
        + 0.25 * (final_confidence or 0.0)
        + 0.20 * _device_criticality(device)
        + 0.10 * anomaly_norm
        + 0.10 * (1.0 if patient_at_risk else 0.0)
    )
    return round(risk, 2)


def _build_title_description(*, detection, device: Device | None, attack_type) -> tuple[str, str]:
    device_label = device.device_uid if device else (
        f"device #{detection.device_id}" if detection.device_id else "an unidentified device"
    )

    if detection.final_verdict == "data_integrity":
        title = f"Implausible vitals reported by {device_label}"
        description = (
            f"Stage 4 (vitals forecaster) found the reported readings inconsistent with "
            f"this device's own recent history — the worst vital was "
            f"{float(detection.stage4_max_zscore or 0):.2f} standard deviations off the "
            f"forecast. Stage 1 flow probability was "
            f"{float(detection.stage1_probability or 0):.3f}."
        )
    elif attack_type is not None:
        title = f"{attack_type.display_name} detected on {device_label}"
        description = (
            f"Stage 1 flagged this flow malicious (p={float(detection.stage1_probability or 0):.3f}); "
            f"Stage 2 attributed it to {attack_type.display_name} "
            f"(confidence={float(detection.stage2_confidence or 0):.3f})."
        )
    elif detection.final_verdict == "zero_day_suspect":
        title = f"Possible zero-day / unrecognised attack on {device_label}"
        description = (
            f"Stage 3 (autoencoder) flagged this flow as anomalous "
            f"(anomaly score={float(detection.stage3_anomaly_score or 0):.3f}, threshold=1.0), "
            f"but no known attack signature matched it."
        )
    else:
        title = f"Suspicious activity on {device_label}"
        description = (
            f"Detection #{detection.id} was flagged severity={detection.severity} "
            f"but did not confidently match a known attack family."
        )
    return title, description


def _generate_recommendations(db: Session, alert: Alert, *, attack_type, device: Device | None,
                              verdict: str | None = None) -> None:
    is_life_critical = bool(device and device.device_type and device.device_type.is_life_critical)
    recs: list[MitigationRecommendation] = []

    if verdict == "data_integrity":
        # The readings themselves are in question, so the first action is
        # clinical, not network: stop trusting the numbers until confirmed.
        recs.append(MitigationRecommendation(
            alert_id=alert.id,
            recommendation=(
                "Confirm this patient's condition from a bedside or redundant sensor "
                "before acting on any reading from this device."
            ),
            action_type="notify_biomed",
            target=device.device_uid if device else None,
            requires_approval=True,
        ))
        recs.append(MitigationRecommendation(
            alert_id=alert.id,
            recommendation=(
                "Re-authenticate the device and verify its firmware and sensor calibration — "
                "implausible vitals can come from tampering or from a failing sensor."
            ),
            action_type="force_reauth",
            target=device.device_uid if device else None,
            requires_approval=True,
        ))
    elif attack_type is not None and attack_type.code == "DATA_ALTERATION":
        recs.append(MitigationRecommendation(
            alert_id=alert.id,
            recommendation="Cross-check the reported vitals against a redundant sensor or bedside reading before acting on them.",
            action_type="notify_biomed",
            target=device.device_uid if device else None,
            requires_approval=True,
        ))
        recs.append(MitigationRecommendation(
            alert_id=alert.id,
            recommendation="Investigate for a man-in-the-middle position on this device's network segment.",
            action_type="manual_review",
            requires_approval=True,
        ))
    elif attack_type is not None and attack_type.code == "SPOOFING_MITM":
        recs.append(MitigationRecommendation(
            alert_id=alert.id,
            recommendation=(
                f"Verify the MAC/IP binding for {device.device_uid if device else 'this device'} "
                "against the registry; isolate the suspected attacker host if confirmed."
            ),
            action_type="isolate_source",
            target=device.ip_address if device else None,
            is_automatable=not is_life_critical,
            requires_approval=True,
        ))
    else:
        recs.append(MitigationRecommendation(
            alert_id=alert.id,
            recommendation="Manually review this detection — no known attack family was confidently matched.",
            action_type="manual_review",
            requires_approval=True,
        ))

    # doc §14.3 safety rule: never automatable for a life-critical device, full stop.
    if is_life_critical:
        for r in recs:
            r.is_automatable = False

    db.add_all(recs)


def _find_open_alert(db: Session, *, device_id: int | None, attack_type_id: int | None) -> Alert | None:
    if device_id is None:
        return None
    query = db.query(Alert).filter(
        Alert.device_id == device_id,
        Alert.status.notin_(["resolved", "false_positive"]),
    )
    query = query.filter(Alert.attack_type_id == attack_type_id) if attack_type_id is not None \
        else query.filter(Alert.attack_type_id.is_(None))
    return query.order_by(Alert.last_seen_at.desc()).first()


def maybe_create_alert(db: Session, *, detection) -> Alert | None:
    """Called right after a detection is persisted. Returns the (possibly
    deduplicated) alert, or None if this detection isn't alert-worthy."""
    if detection.severity not in ALERT_SEVERITIES:
        return None

    device = db.query(Device).filter(Device.id == detection.device_id).first() if detection.device_id else None
    attack_type = detection.stage2_attack_type
    patient_assignment = None
    if device is not None:
        patient_assignment = (
            db.query(PatientDeviceAssignment)
            .filter(PatientDeviceAssignment.device_id == device.id, PatientDeviceAssignment.released_at.is_(None))
            .first()
        )

    now = detection.detected_at
    risk_score = _compute_risk_score(
        severity=detection.severity,
        final_confidence=float(detection.final_confidence) if detection.final_confidence is not None else 0.0,
        device=device,
        stage3_anomaly_score=float(detection.stage3_anomaly_score) if detection.stage3_anomaly_score is not None else None,
        patient_at_risk=patient_assignment is not None,
    )

    existing = _find_open_alert(db, device_id=detection.device_id, attack_type_id=detection.stage2_attack_type_id)
    if existing is not None:
        existing.occurrence_count += 1
        existing.last_seen_at = now
        if risk_score > float(existing.risk_score or 0):
            existing.risk_score = risk_score
        db.commit()
        db.refresh(existing)
        return existing

    title, description = _build_title_description(detection=detection, device=device, attack_type=attack_type)

    alert = Alert(
        alert_uid=f"ALT-TMP-{uuid.uuid4().hex[:10]}",
        detection_id=detection.id,
        device_id=detection.device_id,
        patient_id=patient_assignment.patient_id if patient_assignment else None,
        attack_type_id=detection.stage2_attack_type_id,
        title=title,
        description=description,
        severity=detection.severity,
        risk_score=risk_score,
        status="new",
        occurrence_count=1,
        first_seen_at=now,
        last_seen_at=now,
    )
    db.add(alert)
    db.flush()  # assigns alert.id

    alert.alert_uid = f"ALT-{now.year}-{alert.id:06d}"
    db.add(AlertAction(alert_id=alert.id, user_id=None, action="created", new_status="new"))
    _generate_recommendations(db, alert, attack_type=attack_type, device=device,
                              verdict=detection.final_verdict)
    notification_service.dispatch_for_alert(db, alert=alert)

    db.commit()
    db.refresh(alert)
    return alert


def _get_or_404(db: Session, alert_id: int) -> Alert:
    alert = db.query(Alert).filter(Alert.id == alert_id).first()
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
    return alert


def _write_action(db: Session, alert: Alert, *, user_id: int | None, action: str, comment: str | None = None,
                   previous_status: str | None = None, new_status: str | None = None) -> None:
    db.add(AlertAction(
        alert_id=alert.id, user_id=user_id, action=action, comment=comment,
        previous_status=previous_status, new_status=new_status,
    ))


def list_alerts(db: Session, *, page: int, size: int, status_filter: str | None = None,
                 severity: str | None = None, device_id: int | None = None):
    query = db.query(Alert)
    if status_filter:
        query = query.filter(Alert.status == status_filter)
    if severity:
        query = query.filter(Alert.severity == severity)
    if device_id is not None:
        query = query.filter(Alert.device_id == device_id)
    query = query.order_by(Alert.risk_score.desc(), Alert.last_seen_at.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total


def get_alert(db: Session, alert_id: int) -> Alert | None:
    return db.query(Alert).filter(Alert.id == alert_id).first()


def list_alert_actions(db: Session, alert_id: int) -> list[AlertAction]:
    return (
        db.query(AlertAction)
        .filter(AlertAction.alert_id == alert_id)
        .order_by(AlertAction.created_at.asc())
        .all()
    )


def list_mitigation_recommendations(db: Session, alert_id: int) -> list[MitigationRecommendation]:
    return db.query(MitigationRecommendation).filter(MitigationRecommendation.alert_id == alert_id).all()


def get_recommendation(db: Session, *, alert_id: int, recommendation_id: int) -> MitigationRecommendation | None:
    return (
        db.query(MitigationRecommendation)
        .filter(MitigationRecommendation.id == recommendation_id,
                MitigationRecommendation.alert_id == alert_id)
        .first()
    )


def acknowledge_alert(db: Session, *, alert_id: int, actor_user_id: int) -> Alert:
    alert = _get_or_404(db, alert_id)
    if alert.status in ("resolved", "false_positive"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"alert is already {alert.status}")
    previous = alert.status
    alert.status = "acknowledged"
    alert.acknowledged_at = datetime.utcnow()
    _write_action(db, alert, user_id=actor_user_id, action="acknowledged", previous_status=previous, new_status="acknowledged")
    db.commit()
    db.refresh(alert)
    return alert


def assign_alert(db: Session, *, alert_id: int, assignee_user_id: int, actor_user_id: int) -> Alert:
    alert = _get_or_404(db, alert_id)
    assignee = db.query(User).filter(User.id == assignee_user_id, User.deleted_at.is_(None)).first()
    if assignee is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "unknown assignee")
    previous = alert.status
    alert.assigned_to = assignee_user_id
    if alert.status == "new":
        alert.status = "investigating"
    _write_action(
        db, alert, user_id=actor_user_id, action="assigned", comment=f"assigned to {assignee.username}",
        previous_status=previous, new_status=alert.status,
    )
    db.commit()
    db.refresh(alert)
    return alert


def resolve_alert(db: Session, *, alert_id: int, notes: str | None, actor_user_id: int) -> Alert:
    alert = _get_or_404(db, alert_id)
    if alert.status in ("resolved", "false_positive"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"alert is already {alert.status}")
    previous = alert.status
    alert.status = "resolved"
    alert.resolved_at = datetime.utcnow()
    alert.resolution_notes = notes
    _write_action(db, alert, user_id=actor_user_id, action="resolved", comment=notes, previous_status=previous, new_status="resolved")
    db.commit()
    db.refresh(alert)
    return alert


def mark_false_positive(db: Session, *, alert_id: int, notes: str | None, actor_user_id: int) -> Alert:
    alert = _get_or_404(db, alert_id)
    if alert.status in ("resolved", "false_positive"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"alert is already {alert.status}")
    previous = alert.status
    alert.status = "false_positive"
    alert.resolved_at = datetime.utcnow()
    alert.resolution_notes = notes
    _write_action(
        db, alert, user_id=actor_user_id, action="marked_false_positive", comment=notes,
        previous_status=previous, new_status="false_positive",
    )
    db.commit()
    db.refresh(alert)
    return alert


def comment_on_alert(db: Session, *, alert_id: int, comment: str, actor_user_id: int) -> Alert:
    alert = _get_or_404(db, alert_id)
    _write_action(db, alert, user_id=actor_user_id, action="commented", comment=comment,
                  previous_status=alert.status, new_status=alert.status)
    db.commit()
    db.refresh(alert)
    return alert


def _blocklist(db: Session, *, alert: Alert, entry_type: str, value: str, actor_user_id: int) -> None:
    """Adds a blocklist row inside the caller's transaction. Deliberately not
    blocklist_service.create_entry(), which commits on its own — applying a
    recommendation has to land as one unit with the audit trail beside it."""
    existing = (
        db.query(BlocklistEntry)
        .filter(
            BlocklistEntry.entry_type == entry_type,
            BlocklistEntry.value == value,
            BlocklistEntry.is_active.is_(True),
        )
        .first()
    )
    if existing is not None:
        return  # already blocked; applying again shouldn't stack duplicate rows
    db.add(BlocklistEntry(
        entry_type=entry_type,
        value=value,
        reason=f"Mitigation applied for {alert.alert_uid}",
        alert_id=alert.id,
        added_by=actor_user_id,
    ))


def _apply_effect(db: Session, *, rec: MitigationRecommendation, alert: Alert,
                  device: Device | None, actor_user_id: int) -> str:
    """Carries out the recommendation. Returns a human-readable description of
    what actually changed, for the alert timeline and the audit log."""
    if rec.action_type == "block_ip":
        value = rec.target or (device.ip_address if device else None)
        if not value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "no IP to block — the recommendation has no target and the device has no IP on record",
            )
        _blocklist(db, alert=alert, entry_type="ip", value=value, actor_user_id=actor_user_id)
        return f"blocked IP {value}"

    if rec.action_type == "revoke_mqtt_client":
        value = rec.target or (device.mqtt_client_id if device else None)
        if not value:
            raise HTTPException(
                status.HTTP_400_BAD_REQUEST,
                "no MQTT client ID to revoke — none on the recommendation or the device",
            )
        _blocklist(db, alert=alert, entry_type="mqtt_client", value=value, actor_user_id=actor_user_id)
        return f"revoked MQTT client {value}"

    if rec.action_type == "isolate_source":
        if device is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot isolate — this alert has no device")
        parts = []
        if device.status != "quarantined":
            device.status = "quarantined"
            parts.append(f"quarantined {device.device_uid}")
        ip = rec.target or device.ip_address
        if ip:
            _blocklist(db, alert=alert, entry_type="ip", value=ip, actor_user_id=actor_user_id)
            parts.append(f"blocked IP {ip}")
        return ", ".join(parts) if parts else f"{device.device_uid} was already quarantined"

    return "recorded — this step is carried out off-platform"


def apply_recommendation(db: Session, *, alert_id: int, recommendation_id: int, actor_user_id: int,
                         confirm_life_critical: bool = False) -> dict:
    alert = _get_or_404(db, alert_id)
    if alert.status in ("resolved", "false_positive"):
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"alert is already {alert.status}")

    rec = get_recommendation(db, alert_id=alert_id, recommendation_id=recommendation_id)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recommendation not found on this alert")
    if rec.applied:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "recommendation has already been applied")

    device = db.query(Device).filter(Device.id == alert.device_id).first() if alert.device_id else None
    is_life_critical = bool(device and device.device_type and device.device_type.is_life_critical)
    enforcing = rec.action_type in ENFORCING_ACTIONS

    # doc §14.3: a life-critical device is never cut off automatically. A person
    # can still do it, but only by saying so explicitly — cutting a ventilator
    # off the network to stop an attack can be worse than the attack.
    if enforcing and is_life_critical and not confirm_life_critical:
        raise HTTPException(
            status.HTTP_409_CONFLICT,
            f"{device.device_uid} is life-critical: applying '{rec.action_type}' can interrupt patient care. "
            "Re-send with confirm_life_critical=true to take responsibility for that.",
        )

    effect = _apply_effect(db, rec=rec, alert=alert, device=device, actor_user_id=actor_user_id)

    rec.applied = True
    rec.applied_by = actor_user_id
    rec.applied_at = datetime.utcnow()

    comment = f"Applied mitigation '{rec.action_type}': {effect}"
    if enforcing and is_life_critical:
        comment += " (confirmed on a life-critical device)"
    previous = alert.status
    if alert.status == "new":
        alert.status = "investigating"
    _write_action(db, alert, user_id=actor_user_id, action="mitigated", comment=comment,
                  previous_status=previous, new_status=alert.status)

    db.commit()
    db.refresh(rec)
    db.refresh(alert)
    return {"recommendation": rec, "alert": alert, "effect": effect, "enforcing": enforcing}
