from datetime import datetime
from typing import Optional

from pydantic import BaseModel


class NotificationOut(BaseModel):
    id: int
    alert_id: int
    alert_uid: Optional[str] = None
    channel: str
    recipient: Optional[str] = None
    payload: Optional[dict] = None
    status: str
    retry_count: int
    error_message: Optional[str] = None
    sent_at: Optional[datetime] = None


class NotificationListResponse(BaseModel):
    items: list[NotificationOut]
    total: int
    page: int
    size: int
