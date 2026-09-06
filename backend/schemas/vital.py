from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class VitalIngestRequest(BaseModel):
    device_id: int
    patient_id: Optional[int] = None
    recorded_at: Optional[datetime] = Field(default=None, description="defaults to now (UTC)")
    heart_rate: Optional[int] = Field(default=None, ge=0, le=300)
    spo2: Optional[int] = Field(default=None, ge=0, le=100)
    systolic_bp: Optional[int] = Field(default=None, ge=0, le=300)
    diastolic_bp: Optional[int] = Field(default=None, ge=0, le=200)
    body_temp: Optional[float] = Field(default=None, ge=0, le=50)
    respiration_rate: Optional[int] = Field(default=None, ge=0, le=120)
    raw_payload: Optional[dict] = None


class VitalOut(BaseModel):
    id: int
    device_id: int
    patient_id: Optional[int] = None
    recorded_at: datetime
    heart_rate: Optional[int] = None
    spo2: Optional[int] = None
    systolic_bp: Optional[int] = None
    diastolic_bp: Optional[int] = None
    body_temp: Optional[float] = None
    respiration_rate: Optional[int] = None
    is_plausible: bool
    predicted_values: Optional[dict] = None
    residual_zscore: Optional[float] = None
    injection_suspected: bool
    # False when Stage 4 could not run for this reading (no active model, first
    # WINDOW readings for the device, or a sensor dropout in the window).
    stage4_evaluated: bool


class VitalListResponse(BaseModel):
    items: list[VitalOut]
    total: int
    page: int
    size: int
