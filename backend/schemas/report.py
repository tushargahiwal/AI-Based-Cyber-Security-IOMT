from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

REPORT_TYPES = ("daily", "weekly", "incident", "compliance", "custom", "patient", "device", "ward")


class ReportCreateRequest(BaseModel):
    report_type: str = Field(pattern="^(daily|weekly|incident|compliance|custom|patient|device|ward)$")
    title: Optional[str] = Field(default=None, max_length=200)
    # daily/weekly infer their own window, patient/device fall back to 30 days;
    # incident/compliance/custom must be told what they cover.
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = Field(default=None, description="defaults to now (UTC)")

    # Scope. patient_id and device_id narrow to one subject's devices; ward
    # narrows to a ward's devices; severity and verdict filter what is counted.
    patient_id: Optional[int] = None
    device_id: Optional[int] = None
    ward: Optional[str] = Field(default=None, max_length=60)
    severity: Optional[str] = Field(default=None, pattern="^(info|low|medium|high|critical)$")
    verdict: Optional[str] = Field(
        default=None,
        pattern="^(benign|known_attack|zero_day_suspect|data_integrity|uncertain)$",
    )

    def scope_filters(self) -> dict:
        return {
            "patient_id": self.patient_id,
            "device_id": self.device_id,
            "ward": self.ward,
            "severity": self.severity,
            "verdict": self.verdict,
        }


class ReportOut(BaseModel):
    id: int
    report_type: str
    title: Optional[str] = None
    period_start: Optional[datetime] = None
    period_end: Optional[datetime] = None
    filters: Optional[dict] = None
    summary_stats: Optional[dict] = None
    generated_by: Optional[int] = None
    generated_by_username: Optional[str] = None
    created_at: Optional[datetime] = None


class ReportAuthor(BaseModel):
    id: int
    username: str
    reports: int


class ReportListResponse(BaseModel):
    items: list[ReportOut]
    total: int
    page: int
    size: int
    # Everyone who has generated a report, so the filter can be built without
    # users.manage — an analyst can see whose reports these are without being
    # able to list the user directory.
    authors: list[ReportAuthor] = []
