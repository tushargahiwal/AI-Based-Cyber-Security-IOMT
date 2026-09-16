"""Undoing and expiring mitigations.

Applying a mitigation is a one-way door in most security tools. In a hospital it
cannot be: quarantining a ventilator to stop an attack can be worse than the
attack, and the mistake is usually noticed minutes later by someone who needs a
way to put it back. So every enforcing action here is reversible by hand and
expires on its own.

The expiry is the more important half. A device cut off during a night shift and
then forgotten because the analyst went home is a patient-safety incident the
system caused. `release_expired()` runs on a timer and puts those devices back.
"""

import logging
from datetime import datetime, timedelta

from sqlalchemy.orm import Session

from models.alert import Alert
from models.alert_action import AlertAction
from models.blocklist import BlocklistEntry
from models.device import Device
from models.mitigation_recommendation import MitigationRecommendation

logger = logging.getLogger(__name__)

# How long an automatic quarantine lasts before it lifts itself. Short enough
# that a forgotten one does not run into the next shift, long enough for an
# analyst to finish triaging. An operator who wants it held longer re-applies it.
QUARANTINE_HOURS = 4
BLOCK_HOURS = 24

# The sweep interval. A device is released within this long of its deadline;
# a minute of overshoot on a four-hour quarantine does not matter, and polling
# harder would just add load for nothing.
SWEEP_SECONDS = 60


def quarantine_deadline(now: datetime | None = None) -> datetime:
    return (now or datetime.utcnow()) + timedelta(hours=QUARANTINE_HOURS)


def block_deadline(now: datetime | None = None) -> datetime:
    return (now or datetime.utcnow()) + timedelta(hours=BLOCK_HOURS)


def active_blocklist_filter(query, now: datetime | None = None):
    """Restricts a blocklist query to entries that are actually in force.

    `expires_at` was being stored and never read, so an expired block still
    looked active everywhere it was listed. A NULL expiry means indefinite.
    """
    moment = now or datetime.utcnow()
    return query.filter(
        BlocklistEntry.is_active.is_(True),
        (BlocklistEntry.expires_at.is_(None)) | (BlocklistEntry.expires_at > moment),
    )


def release_expired(db: Session, *, now: datetime | None = None) -> dict:
    """Lifts quarantines and blocks whose deadline has passed.

    Safe to call repeatedly and from a timer; it only touches rows that are
    already past their own deadline.
    """
    moment = now or datetime.utcnow()
    released_devices = []

    devices = (
        db.query(Device)
        .filter(Device.status == "quarantined",
                Device.quarantined_until.isnot(None),
                Device.quarantined_until <= moment)
        .all()
    )
    for device in devices:
        device.status = "online"
        device.quarantined_until = None
        released_devices.append(device.device_uid)
        # Recorded against the alert that caused it, so the timeline shows the
        # release rather than the device silently coming back.
        alert = (
            db.query(Alert)
            .filter(Alert.device_id == device.id)
            .order_by(Alert.last_seen_at.desc())
            .first()
        )
        if alert is not None:
            db.add(AlertAction(
                alert_id=alert.id, user_id=None, action="reverted",
                comment=f"Quarantine on {device.device_uid} expired and was lifted automatically.",
            ))

    expired_blocks = (
        db.query(BlocklistEntry)
        .filter(BlocklistEntry.is_active.is_(True),
                BlocklistEntry.expires_at.isnot(None),
                BlocklistEntry.expires_at <= moment)
        .all()
    )
    for entry in expired_blocks:
        entry.is_active = False

    if released_devices or expired_blocks:
        db.commit()
        logger.info("safety sweep: released %s, expired %d blocklist entries",
                    released_devices or "no devices", len(expired_blocks))

    return {
        "checked_at": moment,
        "devices_released": released_devices,
        "blocklist_entries_expired": len(expired_blocks),
    }


def revert_mitigation(db: Session, *, recommendation: MitigationRecommendation, alert: Alert,
                      actor_user_id: int, reason: str | None = None) -> str:
    """Puts back what an applied mitigation changed. Returns what it undid.

    Only the enforcing side is reversible — un-quarantining a device and
    deactivating the blocks raised for this alert. An advisory step ("we called
    biomed") cannot be un-done by software, so reverting one only clears the
    record that it was taken.
    """
    undone = []

    device = db.query(Device).filter(Device.id == alert.device_id).first() if alert.device_id else None
    if device is not None and device.status == "quarantined":
        device.status = "online"
        device.quarantined_until = None
        undone.append(f"released {device.device_uid} from quarantine")

    blocks = (
        db.query(BlocklistEntry)
        .filter(BlocklistEntry.alert_id == alert.id, BlocklistEntry.is_active.is_(True))
        .all()
    )
    for entry in blocks:
        entry.is_active = False
        undone.append(f"lifted {entry.entry_type} block on {entry.value}")

    recommendation.applied = False
    recommendation.applied_by = None
    recommendation.applied_at = None

    effect = ", ".join(undone) if undone else "nothing to undo — this step was advisory only"
    comment = f"Reverted mitigation '{recommendation.action_type}': {effect}"
    if reason:
        comment += f" — {reason}"
    db.add(AlertAction(alert_id=alert.id, user_id=actor_user_id, action="reverted", comment=comment))

    db.commit()
    db.refresh(recommendation)
    return effect
