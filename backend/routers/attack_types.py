from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, get_current_user, require_permission
from schemas.attack_type import AttackTypeCreateRequest, AttackTypeOut, AttackTypeUpdateRequest
from services import attack_type_service, audit_service

router = APIRouter(prefix="/api/v1/attack-types", tags=["attack-types"])


@router.get("", response_model=list[AttackTypeOut])
def list_attack_types(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    return [AttackTypeOut.model_validate(a) for a in attack_type_service.list_attack_types(db)]


@router.post("", response_model=AttackTypeOut, status_code=status.HTTP_201_CREATED)
def create_attack_type(
    body: AttackTypeCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    attack_type = attack_type_service.create_attack_type(db, data=body.model_dump())
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="CREATE_ATTACK_TYPE",
        entity_type="attack_types",
        entity_id=attack_type.id,
        new_value={"code": attack_type.code, "family": attack_type.family},
        ip_address=request.client.host if request.client else None,
    )
    return AttackTypeOut.model_validate(attack_type)


@router.get("/{attack_type_id}", response_model=AttackTypeOut)
def get_attack_type(
    attack_type_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    attack_type = attack_type_service.get_attack_type(db, attack_type_id)
    if attack_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attack_type not found")
    return AttackTypeOut.model_validate(attack_type)


@router.patch("/{attack_type_id}", response_model=AttackTypeOut)
def update_attack_type(
    attack_type_id: int,
    body: AttackTypeUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    updates = body.model_dump(exclude_unset=True)
    attack_type = attack_type_service.update_attack_type(
        db, attack_type_id=attack_type_id, updates=updates
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="UPDATE_ATTACK_TYPE",
        entity_type="attack_types",
        entity_id=attack_type_id,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return AttackTypeOut.model_validate(attack_type)
