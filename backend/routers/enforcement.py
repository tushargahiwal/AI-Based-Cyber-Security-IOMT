from typing import Optional

from fastapi import APIRouter, Depends, HTTPException, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from services import alert_service, audit_service, enforcement, enforcement_service

router = APIRouter(prefix="/api/v1/enforcement", tags=["enforcement"])


class ExecuteRequest(BaseModel):
    actuator: str = Field(description="which planned action to carry out")
    confirm_medical_device: bool = Field(
        default=False,
        description=("required when the target is a registered medical device. "
                     "A life-critical one should almost never be the answer — "
                     "isolate the ward segment instead."),
    )


class ActuatorStatus(BaseModel):
    name: str
    configured: bool
    detail: str
    dry_run: bool
    live: bool


class EnforcementStatus(BaseModel):
    enforcement_enabled: bool
    actuators: list[ActuatorStatus]
    live_count: int


@router.get("/status", response_model=EnforcementStatus)
def enforcement_status(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    """What can act on the network right now, and what is only rehearsing.

    Worth checking before an incident rather than during one: an actuator that
    is configured but still in dry run will log a convincing description of
    something it did not do.
    """
    return EnforcementStatus(**enforcement.status(db))


@router.get("/alerts/{alert_id}/plan")
def enforcement_plan(
    alert_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("alerts.read")),
):
    """What could be done about this alert, and against whom — without doing it.

    The `adversary` block is the part to read. It says which host would be acted
    on and why, because the failure that matters here is cutting off the medical
    device instead of the attacker.
    """
    alert = alert_service.get_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")
    return enforcement_service.plan(db, alert=alert)


@router.post("/alerts/{alert_id}/execute")
def execute_enforcement(
    alert_id: int,
    body: ExecuteRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.quarantine")),
):
    """Carry out one planned action.

    Needs devices.quarantine — this changes the state of the network, not just
    the record of it. Whether anything actually happens also depends on the
    global switch and the actuator's own flag; when either is off the call
    succeeds and reports what it *would* have done.
    """
    alert = alert_service.get_alert(db, alert_id)
    if alert is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "alert not found")

    result = enforcement_service.execute(
        db, alert=alert, actuator_name=body.actuator,
        confirm_medical_device=body.confirm_medical_device,
    )

    alert_service._write_action(
        db, alert, user_id=ctx.user.id, action="mitigated",
        comment=f"Enforcement [{result['actuator']}] {result['summary']}",
    )
    db.commit()

    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="ENFORCEMENT_EXECUTED",
        entity_type="alert",
        entity_id=alert_id,
        new_value={
            "actuator": result["actuator"],
            "target": result["target"],
            "dry_run": result["dry_run"],
            "succeeded": result["succeeded"],
            "adversary": result["adversary"],
            "confirmed_medical_device": body.confirm_medical_device,
        },
        ip_address=request.client.host if request.client else None,
    )
    return result


class KillSwitchRequest(BaseModel):
    enabled: bool
    reason: Optional[str] = Field(default=None, max_length=300)


@router.post("/kill-switch", response_model=EnforcementStatus)
def set_kill_switch(
    body: KillSwitchRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("system_config.write")),
):
    """Turn all enforcement on or off, immediately and without a restart.

    Off is the safe position and the default. If this system ever starts acting
    on the network in a way nobody understands, this is the one call that stops
    it — which is why it is a single flag read on every action rather than
    something cached at startup.
    """
    from services import system_config_service

    existing = system_config_service.get_config(db, enforcement.KILL_SWITCH_KEY)
    value = "true" if body.enabled else "false"
    if existing is None:
        system_config_service.create_config(
            db,
            config_key=enforcement.KILL_SWITCH_KEY,
            config_value=value,
            value_type="bool",
            description="Master switch for all network enforcement actions.",
            actor_user_id=ctx.user.id,
        )
    else:
        system_config_service.update_config(
            db,
            config_key=enforcement.KILL_SWITCH_KEY,
            updates={"config_value": value},
            actor_user_id=ctx.user.id,
        )

    audit_service.log(
        db, user_id=ctx.user.id,
        action="ENFORCEMENT_KILL_SWITCH",
        entity_type="system_config",
        new_value={"enabled": body.enabled, "reason": body.reason},
        ip_address=request.client.host if request.client else None,
    )
    return EnforcementStatus(**enforcement.status(db))
