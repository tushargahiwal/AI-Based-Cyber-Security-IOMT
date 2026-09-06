from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.blocklist import BlocklistCreateRequest, BlocklistOut, BlocklistUpdateRequest
from services import audit_service, blocklist_service

router = APIRouter(prefix="/api/v1/blocklist", tags=["blocklist"])


@router.get("", response_model=list[BlocklistOut])
def list_entries(
    entry_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    return [
        BlocklistOut.model_validate(e)
        for e in blocklist_service.list_entries(db, entry_type=entry_type, is_active=is_active)
    ]


@router.post("", response_model=BlocklistOut, status_code=status.HTTP_201_CREATED)
def create_entry(
    body: BlocklistCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.quarantine")),
):
    entry = blocklist_service.create_entry(
        db,
        entry_type=body.entry_type,
        value=body.value,
        reason=body.reason,
        alert_id=body.alert_id,
        expires_at=body.expires_at,
        actor_user_id=ctx.user.id,
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="CREATE_BLOCKLIST_ENTRY",
        entity_type="blocklist",
        entity_id=entry.id,
        new_value={"entry_type": entry.entry_type, "value": entry.value, "reason": entry.reason},
        ip_address=request.client.host if request.client else None,
    )
    return BlocklistOut.model_validate(entry)


@router.get("/{entry_id}", response_model=BlocklistOut)
def get_entry(
    entry_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    entry = blocklist_service.get_entry(db, entry_id)
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "blocklist entry not found")
    return BlocklistOut.model_validate(entry)


@router.patch("/{entry_id}", response_model=BlocklistOut)
def update_entry(
    entry_id: int,
    body: BlocklistUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.quarantine")),
):
    updates = body.model_dump(exclude_unset=True)
    entry = blocklist_service.update_entry(db, entry_id=entry_id, updates=updates)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="UPDATE_BLOCKLIST_ENTRY",
        entity_type="blocklist",
        entity_id=entry_id,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return BlocklistOut.model_validate(entry)


@router.delete("/{entry_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_entry(
    entry_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.quarantine")),
):
    blocklist_service.delete_entry(db, entry_id=entry_id)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="DELETE_BLOCKLIST_ENTRY",
        entity_type="blocklist",
        entity_id=entry_id,
        ip_address=request.client.host if request.client else None,
    )
