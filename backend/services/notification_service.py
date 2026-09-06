"""Alert notifications (doc §11.4).

Every alert that gets raised produces a notification row per configured channel.
Only the `websocket` channel actually delivers here — email/SMS/telegram/webhook
need credentials and an outbound gateway this deployment does not have, so their
rows are recorded as `pending` with the reason on them. That is on purpose: the
record of who *should* have been told survives even when nothing could send, and
wiring a real transport later means filling in one dispatch function, not
retrofitting the whole trail.
"""

from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.alert import Alert
from models.notification import Notification
from services.broadcast import broadcaster

# Severities worth interrupting someone for. Alerts below this still exist and
# show on the dashboard; they just don't push.
NOTIFY_SEVERITIES = {"high", "critical"}

UNSUPPORTED_CHANNEL_REASON = "no outbound gateway configured for this channel"


def _payload(alert: Alert) -> dict:
    return {
        "alert_uid": alert.alert_uid,
        "title": alert.title,
        "severity": alert.severity,
        "risk_score": float(alert.risk_score) if alert.risk_score is not None else None,
        "device_id": alert.device_id,
        "detection_id": alert.detection_id,
    }


def dispatch_for_alert(db: Session, *, alert: Alert, channels: list[str] | None = None) -> list[Notification]:
    """Records and, where possible, sends notifications for a new alert.

    Called inside the caller's transaction — it adds rows but does not commit,
    so an alert and its notifications land together or not at all.
    """
    if alert.severity not in NOTIFY_SEVERITIES:
        return []

    payload = _payload(alert)
    created: list[Notification] = []

    for channel in channels or ["websocket"]:
        notification = Notification(
            alert_id=alert.id,
            channel=channel,
            payload=payload,
            status="pending",
        )
        if channel == "websocket":
            broadcaster.publish({"type": "alert", "data": payload})
            notification.status = "sent"
            notification.sent_at = datetime.utcnow()
        else:
            notification.error_message = UNSUPPORTED_CHANNEL_REASON
        db.add(notification)
        created.append(notification)

    return created


def list_notifications(db: Session, *, page: int, size: int, status_filter: str | None = None,
                       channel: str | None = None, alert_id: int | None = None):
    query = db.query(Notification)
    if status_filter:
        query = query.filter(Notification.status == status_filter)
    if channel:
        query = query.filter(Notification.channel == channel)
    if alert_id is not None:
        query = query.filter(Notification.alert_id == alert_id)
    query = query.order_by(Notification.id.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total


def retry(db: Session, *, notification_id: int) -> Notification:
    notification = db.query(Notification).filter(Notification.id == notification_id).first()
    if notification is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "notification not found")
    if notification.status == "sent":
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "notification was already sent")

    notification.retry_count += 1
    if notification.channel == "websocket":
        broadcaster.publish({"type": "alert", "data": notification.payload or {}})
        notification.status = "sent"
        notification.sent_at = datetime.utcnow()
        notification.error_message = None
    else:
        notification.status = "failed"
        notification.error_message = UNSUPPORTED_CHANNEL_REASON

    db.commit()
    db.refresh(notification)
    return notification
