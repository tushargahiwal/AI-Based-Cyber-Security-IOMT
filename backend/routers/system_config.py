from fastapi import APIRouter, Depends, HTTPException, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.system_config import SystemConfigCreateRequest, SystemConfigOut, SystemConfigUpdateRequest
from services import audit_service, system_config_service

router = APIRouter(prefix="/api/v1/system-config", tags=["system-config"])


@router.get("", response_model=list[SystemConfigOut])
def list_configs(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    return [SystemConfigOut.model_validate(c) for c in system_config_service.list_configs(db)]


@router.post("", response_model=SystemConfigOut, status_code=status.HTTP_201_CREATED)
def create_config(
    body: SystemConfigCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    config = system_config_service.create_config(
        db,
        config_key=body.config_key,
        config_value=body.config_value,
        value_type=body.value_type,
        description=body.description,
        actor_user_id=ctx.user.id,
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="CREATE_CONFIG",
        entity_type="system_config",
        entity_id=config.id,
        new_value={"config_key": config.config_key, "config_value": config.config_value},
        ip_address=request.client.host if request.client else None,
    )
    return SystemConfigOut.model_validate(config)


@router.get("/{config_key}", response_model=SystemConfigOut)
def get_config(
    config_key: str,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    config = system_config_service.get_config(db, config_key)
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "config key not found")
    return SystemConfigOut.model_validate(config)


@router.patch("/{config_key}", response_model=SystemConfigOut)
def update_config(
    config_key: str,
    body: SystemConfigUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    updates = body.model_dump(exclude_unset=True)
    config = system_config_service.update_config(
        db, config_key=config_key, updates=updates, actor_user_id=ctx.user.id
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="UPDATE_CONFIG",
        entity_type="system_config",
        entity_id=config.id,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return SystemConfigOut.model_validate(config)


@router.delete("/{config_key}", status_code=status.HTTP_204_NO_CONTENT)
def delete_config(
    config_key: str,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    system_config_service.delete_config(db, config_key=config_key)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="DELETE_CONFIG",
        entity_type="system_config",
        old_value={"config_key": config_key},
        ip_address=request.client.host if request.client else None,
    )
