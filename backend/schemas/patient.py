from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

from schemas.device import WardOut


class PatientCreateRequest(BaseModel):
    age_band: Optional[str] = Field(default=None, max_length=16, pattern=r"^\d{1,3}-\d{1,3}$")
    sex: Optional[str] = Field(default=None, pattern="^(M|F|O|U)$")
    ward: Optional[str] = Field(default=None, description="wards.name, e.g. 'ICU-1'")
    baseline_hr_min: Optional[int] = Field(default=None, ge=0, le=400)
    baseline_hr_max: Optional[int] = Field(default=None, ge=0, le=400)
    baseline_spo2_min: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=255)


class PatientUpdateRequest(BaseModel):
    age_band: Optional[str] = Field(default=None, max_length=16, pattern=r"^\d{1,3}-\d{1,3}$")
    sex: Optional[str] = Field(default=None, pattern="^(M|F|O|U)$")
    ward: Optional[str] = None
    baseline_hr_min: Optional[int] = Field(default=None, ge=0, le=400)
    baseline_hr_max: Optional[int] = Field(default=None, ge=0, le=400)
    baseline_spo2_min: Optional[int] = Field(default=None, ge=0, le=100)
    notes: Optional[str] = Field(default=None, max_length=255)
    discharged: Optional[bool] = Field(default=None, description="true discharges the patient now, false re-admits")


class PatientOut(BaseModel):
    id: int
    patient_code: str
    age_band: Optional[str] = None
    sex: Optional[str] = None
    ward: Optional[WardOut] = None
    admitted_at: Optional[datetime] = None
    discharged_at: Optional[datetime] = None
    baseline_hr_min: Optional[int] = None
    baseline_hr_max: Optional[int] = None
    baseline_spo2_min: Optional[int] = None
    notes: Optional[str] = None


class PatientListResponse(BaseModel):
    items: list[PatientOut]
    total: int
    page: int
    size: int


class AssignmentCreateRequest(BaseModel):
    device_id: int


class AssignmentOut(BaseModel):
    id: int
    patient_id: int
    device_id: int
    device_uid: Optional[str] = None
    assigned_at: datetime
    released_at: Optional[datetime] = None
