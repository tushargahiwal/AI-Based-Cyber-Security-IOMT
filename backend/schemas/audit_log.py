from datetime import datetime
from typing import Optional, Union

from pydantic import BaseModel


class AuditLogOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    entity_type: Optional[str] = None
    entity_id: Optional[int] = None
    old_value: Optional[Union[dict, list]] = None
    new_value: Optional[Union[dict, list]] = None
    ip_address: Optional[str] = None
    created_at: Optional[datetime] = None


class AuditLogListResponse(BaseModel):
    items: list[AuditLogOut]
    total: int
    page: int
    size: int
