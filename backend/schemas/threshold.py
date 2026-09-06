from typing import Optional

from pydantic import BaseModel, Field, model_validator

SCOPE_PATTERN = "^(global|device_type|device|patient)$"


class ThresholdCreateRequest(BaseModel):
    scope: str = Field(pattern=SCOPE_PATTERN)
    scope_id: Optional[int] = Field(default=None, description="required unless scope='global'")
    metric: str = Field(min_length=1, max_length=50)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_delta_per_sec: Optional[float] = None
    is_active: bool = True

    @model_validator(mode="after")
    def _check_scope_id(self):
        if self.scope != "global" and self.scope_id is None:
            raise ValueError("scope_id is required unless scope is 'global'")
        return self


class ThresholdUpdateRequest(BaseModel):
    scope: Optional[str] = Field(default=None, pattern=SCOPE_PATTERN)
    scope_id: Optional[int] = None
    metric: Optional[str] = Field(default=None, min_length=1, max_length=50)
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_delta_per_sec: Optional[float] = None
    is_active: Optional[bool] = None


class ThresholdOut(BaseModel):
    id: int
    scope: str
    scope_id: Optional[int] = None
    metric: str
    min_value: Optional[float] = None
    max_value: Optional[float] = None
    max_delta_per_sec: Optional[float] = None
    is_active: bool

    model_config = {"from_attributes": True}
