from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class AlertOut(BaseModel):
    id: int
    alert_uid: str
    detection_id: int
    device_id: Optional[int] = None
    device_uid: Optional[str] = None
    patient_id: Optional[int] = None
    patient_code: Optional[str] = None
    attack_type_id: Optional[int] = None
    attack_family: Optional[str] = None
    title: str
    description: Optional[str] = None
    severity: str
    risk_score: Optional[float] = None
    status: str
    assigned_to: Optional[int] = None
    assignee_username: Optional[str] = None
    occurrence_count: int
    first_seen_at: datetime
    last_seen_at: datetime
    acknowledged_at: Optional[datetime] = None
    resolved_at: Optional[datetime] = None
    resolution_notes: Optional[str] = None
    created_at: Optional[datetime] = None


class AlertListResponse(BaseModel):
    items: list[AlertOut]
    total: int
    page: int
    size: int


class AlertActionOut(BaseModel):
    id: int
    user_id: Optional[int] = None
    username: Optional[str] = None
    action: str
    comment: Optional[str] = None
    previous_status: Optional[str] = None
    new_status: Optional[str] = None
    created_at: Optional[datetime] = None


class MitigationRecommendationOut(BaseModel):
    id: int
    recommendation: str
    action_type: Optional[str] = None
    target: Optional[str] = None
    is_automatable: bool
    requires_approval: bool
    applied: bool
    applied_by: Optional[int] = None
    applied_at: Optional[datetime] = None


class AlertDetailOut(AlertOut):
    actions: list[AlertActionOut] = Field(default_factory=list)
    recommendations: list[MitigationRecommendationOut] = Field(default_factory=list)


class AssignRequest(BaseModel):
    user_id: int


class ResolveRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=2000)


class FalsePositiveRequest(BaseModel):
    notes: Optional[str] = Field(default=None, max_length=2000)


class CommentRequest(BaseModel):
    comment: str = Field(min_length=1, max_length=2000)


class ApplyRecommendationRequest(BaseModel):
    confirm_life_critical: bool = Field(
        default=False,
        description=(
            "Required to apply an enforcing action (isolate/block/revoke) to a life-critical "
            "device. Without it the request is refused with 409."
        ),
    )


class ApplyRecommendationResponse(BaseModel):
    recommendation: MitigationRecommendationOut
    alert: AlertOut
    effect: str = Field(description="what actually changed, in plain words")
    enforcing: bool = Field(description="False when applying only records that a person took this on")
