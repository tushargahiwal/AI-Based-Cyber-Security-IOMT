from datetime import datetime
from typing import Optional

from fastapi import APIRouter, Depends, Request, status
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from services import audit_service, simulation_service

router = APIRouter(prefix="/api/v1/simulate", tags=["simulation"])


class SimulationRequest(BaseModel):
    mode: str = Field(default="mixed", pattern="^(mixed|attack|benign)$")
    rows: int = Field(default=120, ge=1, le=simulation_service.MAX_ROWS)
    speed: float = Field(default=4.0, ge=0, le=50, description="rows per second, 0 for unpaced")
    device_id: Optional[int] = None


class SimulationStatus(BaseModel):
    status: str
    mode: Optional[str] = None
    device_uid: Optional[str] = None
    processed: int
    total: int
    verdicts: dict
    alerts: int
    error: Optional[str] = None
    started_at: Optional[datetime] = None
    finished_at: Optional[datetime] = None


@router.post("", response_model=SimulationStatus, status_code=status.HTTP_202_ACCEPTED)
def start_simulation(
    body: SimulationRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("models.retrain")),
):
    """Replay labelled capture rows through the live pipeline.

    Gated on models.retrain rather than a read permission: this writes real
    detections, alerts and vitals into the database, so it is an operator
    action, not a view.
    """
    state = simulation_service.start(
        db, mode=body.mode, rows=body.rows, speed=body.speed, device_id=body.device_id
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="START_SIMULATION",
        entity_type="simulation",
        new_value={"mode": body.mode, "rows": state["total"], "device_uid": state["device_uid"]},
        ip_address=request.client.host if request.client else None,
    )
    return SimulationStatus(**state)


@router.get("", response_model=SimulationStatus)
def simulation_status(ctx: AuthContext = Depends(require_permission("devices.read"))):
    return SimulationStatus(**simulation_service.get_status())


@router.post("/stop", response_model=SimulationStatus)
def stop_simulation(ctx: AuthContext = Depends(require_permission("models.retrain"))):
    return SimulationStatus(**simulation_service.stop())
