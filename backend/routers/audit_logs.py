from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.audit_log import AuditLogListResponse, AuditLogOut
from services import audit_service

router = APIRouter(prefix="/api/v1/audit-logs", tags=["audit-logs"])


def _to_out(entry) -> AuditLogOut:
    return AuditLogOut(
        id=entry.id,
        user_id=entry.user_id,
        username=entry.user.username if entry.user else None,
        action=entry.action,
        entity_type=entry.entity_type,
        entity_id=entry.entity_id,
        old_value=entry.old_value,
        new_value=entry.new_value,
        ip_address=entry.ip_address,
        created_at=entry.created_at,
    )


@router.get("", response_model=AuditLogListResponse)
def list_audit_logs(
    page: int = Query(1, ge=1),
    size: int = Query(50, ge=1, le=200),
    user_id: int | None = Query(default=None),
    action: str | None = Query(default=None),
    entity_type: str | None = Query(default=None),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("users.manage")),
):
    items, total = audit_service.list_logs(
        db, page=page, size=size, user_id=user_id, action=action, entity_type=entity_type
    )
    return AuditLogListResponse(items=[_to_out(e) for e in items], total=total, page=page, size=size)
