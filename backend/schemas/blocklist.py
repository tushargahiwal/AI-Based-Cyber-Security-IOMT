from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

ENTRY_TYPE_PATTERN = "^(ip|mac|mqtt_client)$"


class BlocklistCreateRequest(BaseModel):
    entry_type: str = Field(pattern=ENTRY_TYPE_PATTERN)
    value: str = Field(min_length=1, max_length=100)
    reason: Optional[str] = Field(default=None, max_length=255)
    alert_id: Optional[int] = None
    expires_at: Optional[datetime] = Field(default=None, description="omit/null = permanent")


class BlocklistUpdateRequest(BaseModel):
    reason: Optional[str] = Field(default=None, max_length=255)
    expires_at: Optional[datetime] = None
    is_active: Optional[bool] = None


class BlocklistOut(BaseModel):
    id: int
    entry_type: str
    value: str
    reason: Optional[str] = None
    alert_id: Optional[int] = None
    added_by: Optional[int] = None
    expires_at: Optional[datetime] = None
    is_active: bool
    created_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
