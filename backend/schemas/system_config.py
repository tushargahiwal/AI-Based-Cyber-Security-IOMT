from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

VALUE_TYPE_PATTERN = "^(string|int|float|bool|json)$"


class SystemConfigCreateRequest(BaseModel):
    config_key: str = Field(min_length=1, max_length=80)
    config_value: Optional[str] = Field(default=None, max_length=255)
    value_type: str = Field(pattern=VALUE_TYPE_PATTERN)
    description: Optional[str] = Field(default=None, max_length=255)


class SystemConfigUpdateRequest(BaseModel):
    config_value: Optional[str] = Field(default=None, max_length=255)
    value_type: Optional[str] = Field(default=None, pattern=VALUE_TYPE_PATTERN)
    description: Optional[str] = Field(default=None, max_length=255)


class SystemConfigOut(BaseModel):
    id: int
    config_key: str
    config_value: Optional[str] = None
    value_type: str
    description: Optional[str] = None
    updated_by: Optional[int] = None
    updated_at: Optional[datetime] = None

    model_config = {"from_attributes": True}
