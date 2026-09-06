from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, get_current_user, require_permission
from schemas.protocol import ProtocolCreateRequest, ProtocolOut, ProtocolUpdateRequest
from services import audit_service, protocol_service

router = APIRouter(prefix="/api/v1/protocols", tags=["protocols"])


@router.get("", response_model=list[ProtocolOut])
def list_protocols(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    return [ProtocolOut.model_validate(p) for p in protocol_service.list_protocols(db)]


@router.post("", response_model=ProtocolOut, status_code=status.HTTP_201_CREATED)
def create_protocol(
    body: ProtocolCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    protocol = protocol_service.create_protocol(
        db, name=body.name, default_port=body.default_port, is_medical=body.is_medical
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="CREATE_PROTOCOL",
        entity_type="protocols",
        entity_id=protocol.id,
        new_value={"name": protocol.name, "default_port": protocol.default_port},
        ip_address=request.client.host if request.client else None,
    )
    return ProtocolOut.model_validate(protocol)


@router.get("/{protocol_id}", response_model=ProtocolOut)
def get_protocol(
    protocol_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    protocol = protocol_service.get_protocol(db, protocol_id)
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "protocol not found")
    return ProtocolOut.model_validate(protocol)


@router.patch("/{protocol_id}", response_model=ProtocolOut)
def update_protocol(
    protocol_id: int,
    body: ProtocolUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    updates = body.model_dump(exclude_unset=True)
    protocol = protocol_service.update_protocol(db, protocol_id=protocol_id, updates=updates)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="UPDATE_PROTOCOL",
        entity_type="protocols",
        entity_id=protocol_id,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return ProtocolOut.model_validate(protocol)
