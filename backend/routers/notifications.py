from fastapi import APIRouter, Depends, HTTPException, Query, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.notification import NotificationListResponse, NotificationOut
from services import notification_service
from services.broadcast import broadcaster

router = APIRouter(prefix="/api/v1/notifications", tags=["notifications"])


def _to_out(n) -> NotificationOut:
    return NotificationOut(
        id=n.id,
        alert_id=n.alert_id,
        alert_uid=n.alert.alert_uid if n.alert else None,
        channel=n.channel,
        recipient=n.recipient,
        payload=n.payload,
        status=n.status,
        retry_count=n.retry_count,
        error_message=n.error_message,
        sent_at=n.sent_at,
    )


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    channel: str | None = Query(default=None),
    alert_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.read")),
):
    items, total = notification_service.list_notifications(
        db, page=page, size=size, status_filter=status_filter, channel=channel, alert_id=alert_id
    )
    return NotificationListResponse(items=[_to_out(n) for n in items], total=total, page=page, size=size)


@router.post("/{notification_id}/retry", response_model=NotificationOut)
def retry_notification(
    notification_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.ack")),
):
    return _to_out(notification_service.retry(db, notification_id=notification_id))


@router.get("/live/status")
def live_status(ctx: AuthContext = Depends(require_permission("alerts.read"))):
    """How many clients the live socket is currently fanning out to.

    Useful when the live monitor looks empty: it separates "nothing is happening"
    from "this browser never actually connected".
    """
    return {"listeners": broadcaster.listener_count}
