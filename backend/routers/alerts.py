from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.alert import (
    AlertActionOut,
    ApplyRecommendationRequest,
    ApplyRecommendationResponse,
    AlertDetailOut,
    AlertListResponse,
    AlertOut,
    AssignRequest,
    CommentRequest,
    FalsePositiveRequest,
    MitigationRecommendationOut,
    ResolveRequest,
)
from services import alert_service, audit_service

router = APIRouter(prefix="/api/v1/alerts", tags=["alerts"])


def _to_out(a) -> AlertOut:
    return AlertOut(
        id=a.id,
        alert_uid=a.alert_uid,
        detection_id=a.detection_id,
        device_id=a.device_id,
        device_uid=a.device.device_uid if a.device else None,
        patient_id=a.patient_id,
        patient_code=a.patient.patient_code if a.patient else None,
        attack_type_id=a.attack_type_id,
        attack_family=a.attack_type.display_name if a.attack_type else None,
        title=a.title,
        description=a.description,
        severity=a.severity,
        risk_score=float(a.risk_score) if a.risk_score is not None else None,
        status=a.status,
        assigned_to=a.assigned_to,
        assignee_username=a.assignee.username if a.assignee else None,
        occurrence_count=a.occurrence_count,
        first_seen_at=a.first_seen_at,
        last_seen_at=a.last_seen_at,
        acknowledged_at=a.acknowledged_at,
        resolved_at=a.resolved_at,
        resolution_notes=a.resolution_notes,
        created_at=a.created_at,
    )


def _rec_to_out(r) -> MitigationRecommendationOut:
    return MitigationRecommendationOut(
        id=r.id, recommendation=r.recommendation, action_type=r.action_type, target=r.target,
        is_automatable=r.is_automatable, requires_approval=r.requires_approval,
        applied=r.applied, applied_by=r.applied_by, applied_at=r.applied_at,
    )


@router.get("", response_model=AlertListResponse)
def list_alerts(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    status_filter: str | None = Query(default=None, alias="status"),
    severity: str | None = Query(default=None),
    device_id: int | None = Query(default=None),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.read")),
):
    items, total = alert_service.list_alerts(
        db, page=page, size=size, status_filter=status_filter, severity=severity, device_id=device_id
    )
    return AlertListResponse(items=[_to_out(a) for a in items], total=total, page=page, size=size)


@router.get("/{alert_id}", response_model=AlertDetailOut)
def get_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.read")),
):
    alert = alert_service.get_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")

    actions = alert_service.list_alert_actions(db, alert_id)
    recs = alert_service.list_mitigation_recommendations(db, alert_id)

    base = _to_out(alert)
    return AlertDetailOut(
        **base.model_dump(),
        actions=[
            AlertActionOut(
                id=act.id, user_id=act.user_id, username=act.user.username if act.user else None,
                action=act.action, comment=act.comment, previous_status=act.previous_status,
                new_status=act.new_status, created_at=act.created_at,
            )
            for act in actions
        ],
        recommendations=[_rec_to_out(r) for r in recs],
    )


@router.post("/{alert_id}/acknowledge", response_model=AlertOut)
def acknowledge_alert(
    alert_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.ack")),
):
    alert = alert_service.acknowledge_alert(db, alert_id=alert_id, actor_user_id=ctx.user.id)
    return _to_out(alert)


@router.post("/{alert_id}/assign", response_model=AlertOut)
def assign_alert(
    alert_id: int,
    body: AssignRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.assign")),
):
    alert = alert_service.assign_alert(db, alert_id=alert_id, assignee_user_id=body.user_id, actor_user_id=ctx.user.id)
    return _to_out(alert)


@router.post("/{alert_id}/resolve", response_model=AlertOut)
def resolve_alert(
    alert_id: int,
    body: ResolveRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.resolve")),
):
    alert = alert_service.resolve_alert(db, alert_id=alert_id, notes=body.notes, actor_user_id=ctx.user.id)
    return _to_out(alert)


@router.post("/{alert_id}/false-positive", response_model=AlertOut)
def mark_false_positive(
    alert_id: int,
    body: FalsePositiveRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.resolve")),
):
    alert = alert_service.mark_false_positive(db, alert_id=alert_id, notes=body.notes, actor_user_id=ctx.user.id)
    return _to_out(alert)


@router.post("/{alert_id}/comment", response_model=AlertOut)
def comment_on_alert(
    alert_id: int,
    body: CommentRequest,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.comment")),
):
    alert = alert_service.comment_on_alert(db, alert_id=alert_id, comment=body.comment, actor_user_id=ctx.user.id)
    return _to_out(alert)

@router.post("/{alert_id}/recommendations/{recommendation_id}/apply",
             response_model=ApplyRecommendationResponse)
def apply_recommendation(
    alert_id: int,
    recommendation_id: int,
    body: ApplyRecommendationRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.ack")),
):
    """Carry out one mitigation recommendation.

    alerts.ack is enough to record an off-platform step (notify biomed, manual
    review). Anything that actually cuts traffic off additionally needs
    devices.quarantine — an analyst who can only triage shouldn't be able to
    isolate a device through this route.
    """
    rec = alert_service.get_recommendation(db, alert_id=alert_id, recommendation_id=recommendation_id)
    if rec is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "recommendation not found on this alert")
    if rec.action_type in alert_service.ENFORCING_ACTIONS:
        if "*" not in ctx.permissions and "devices.quarantine" not in ctx.permissions:
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                f"applying '{rec.action_type}' changes device or network state: "
                "missing permission devices.quarantine",
            )

    result = alert_service.apply_recommendation(
        db,
        alert_id=alert_id,
        recommendation_id=recommendation_id,
        actor_user_id=ctx.user.id,
        confirm_life_critical=body.confirm_life_critical,
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="APPLY_MITIGATION",
        entity_type="mitigation_recommendation",
        entity_id=recommendation_id,
        new_value={
            "alert_id": alert_id,
            "action_type": result["recommendation"].action_type,
            "effect": result["effect"],
            "confirm_life_critical": body.confirm_life_critical,
        },
        ip_address=request.client.host if request.client else None,
    )
    return ApplyRecommendationResponse(
        recommendation=_rec_to_out(result["recommendation"]),
        alert=_to_out(result["alert"]),
        effect=result["effect"],
        enforcing=result["enforcing"],
    )
