from typing import Optional

from pydantic import BaseModel, Field


class DatasetCreateRequest(BaseModel):
    name: str = Field(min_length=1, max_length=100)
    version: Optional[str] = Field(default=None, max_length=20)
    source_url: Optional[str] = Field(default=None, max_length=255)
    total_records: Optional[int] = Field(default=None, ge=0)
    num_features: Optional[int] = Field(default=None, ge=0)
    num_classes: Optional[int] = Field(default=None, ge=0)
    benign_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    citation: Optional[str] = None
    notes: Optional[str] = None


class DatasetUpdateRequest(BaseModel):
    version: Optional[str] = Field(default=None, max_length=20)
    source_url: Optional[str] = Field(default=None, max_length=255)
    total_records: Optional[int] = Field(default=None, ge=0)
    num_features: Optional[int] = Field(default=None, ge=0)
    num_classes: Optional[int] = Field(default=None, ge=0)
    benign_ratio: Optional[float] = Field(default=None, ge=0, le=1)
    citation: Optional[str] = None
    notes: Optional[str] = None


class DatasetOut(BaseModel):
    id: int
    name: str
    version: Optional[str] = None
    source_url: Optional[str] = None
    total_records: Optional[int] = None
    num_features: Optional[int] = None
    num_classes: Optional[int] = None
    benign_ratio: Optional[float] = None
    citation: Optional[str] = None
    notes: Optional[str] = None

    model_config = {"from_attributes": True}
