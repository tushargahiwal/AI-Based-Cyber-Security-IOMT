from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, get_current_user, require_permission
from schemas.threshold import ThresholdCreateRequest, ThresholdOut, ThresholdUpdateRequest
from services import audit_service, threshold_service

router = APIRouter(prefix="/api/v1/thresholds", tags=["thresholds"])


@router.get("", response_model=list[ThresholdOut])
def list_thresholds(
    scope: str | None = Query(default=None),
    metric: str | None = Query(default=None),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    return [
        ThresholdOut.model_validate(t)
        for t in threshold_service.list_thresholds(db, scope=scope, metric=metric)
    ]


@router.post("", response_model=ThresholdOut, status_code=status.HTTP_201_CREATED)
def create_threshold(
    body: ThresholdCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    threshold = threshold_service.create_threshold(db, data=body.model_dump())
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="CREATE_THRESHOLD",
        entity_type="thresholds",
        entity_id=threshold.id,
        new_value={"scope": threshold.scope, "metric": threshold.metric},
        ip_address=request.client.host if request.client else None,
    )
    return ThresholdOut.model_validate(threshold)


@router.get("/{threshold_id}", response_model=ThresholdOut)
def get_threshold(
    threshold_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    threshold = threshold_service.get_threshold(db, threshold_id)
    if threshold is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "threshold not found")
    return ThresholdOut.model_validate(threshold)


@router.patch("/{threshold_id}", response_model=ThresholdOut)
def update_threshold(
    threshold_id: int,
    body: ThresholdUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    updates = body.model_dump(exclude_unset=True)
    threshold = threshold_service.update_threshold(db, threshold_id=threshold_id, updates=updates)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="UPDATE_THRESHOLD",
        entity_type="thresholds",
        entity_id=threshold_id,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return ThresholdOut.model_validate(threshold)


@router.delete("/{threshold_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_threshold(
    threshold_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    threshold_service.delete_threshold(db, threshold_id=threshold_id)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="DELETE_THRESHOLD",
        entity_type="thresholds",
        entity_id=threshold_id,
        ip_address=request.client.host if request.client else None,
    )
