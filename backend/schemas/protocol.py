from typing import Optional

from pydantic import BaseModel, Field


class ProtocolCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=50)
    default_port: Optional[int] = Field(default=None, ge=0, le=65535)
    is_medical: bool = False


class ProtocolUpdateRequest(BaseModel):
    default_port: Optional[int] = Field(default=None, ge=0, le=65535)
    is_medical: Optional[bool] = None


class ProtocolOut(BaseModel):
    id: int
    name: str
    default_port: Optional[int] = None
    is_medical: bool

    model_config = {"from_attributes": True}
