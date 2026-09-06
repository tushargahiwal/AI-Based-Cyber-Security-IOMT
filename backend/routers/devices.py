from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.device import (
    DeviceCreateRequest,
    DeviceListResponse,
    DeviceOut,
    DeviceTypeOut,
    DeviceUpdateRequest,
    WardOut,
)
from services import audit_service, device_service

router = APIRouter(prefix="/api/v1", tags=["devices"])


def _to_device_out(device) -> DeviceOut:
    return DeviceOut(
        id=device.id,
        device_uid=device.device_uid,
        device_type=DeviceTypeOut.model_validate(device.device_type),
        ward=WardOut.model_validate(device.ward) if device.ward else None,
        manufacturer=device.manufacturer,
        model_number=device.model_number,
        firmware_version=device.firmware_version,
        ip_address=device.ip_address,
        mac_address=device.mac_address,
        mqtt_client_id=device.mqtt_client_id,
        status=device.status,
        trust_score=float(device.trust_score),
        last_seen_at=device.last_seen_at,
        created_at=device.created_at,
    )


@router.get("/device-types", response_model=list[DeviceTypeOut])
def list_device_types(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    return [DeviceTypeOut.model_validate(dt) for dt in device_service.list_device_types(db)]


@router.get("/wards", response_model=list[WardOut])
def list_wards(
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    return [WardOut.model_validate(w) for w in device_service.list_wards(db)]


@router.get("/devices", response_model=DeviceListResponse)
def list_devices(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    ward: str | None = Query(default=None),
    device_type: str | None = Query(default=None),
    status_filter: str | None = Query(default=None, alias="status"),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    items, total = device_service.list_devices(
        db, page=page, size=size, ward=ward, device_type=device_type, status_filter=status_filter
    )
    return DeviceListResponse(items=[_to_device_out(d) for d in items], total=total, page=page, size=size)


@router.post("/devices", response_model=DeviceOut, status_code=status.HTTP_201_CREATED)
def register_device(
    body: DeviceCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.write")),
):
    device = device_service.register_device(
        db,
        device_uid=body.device_uid,
        device_type_name=body.device_type,
        ward_name=body.ward,
        manufacturer=body.manufacturer,
        model_number=body.model_number,
        firmware_version=body.firmware_version,
        ip_address=body.ip_address,
        mac_address=body.mac_address,
        mqtt_client_id=body.mqtt_client_id,
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="REGISTER_DEVICE",
        entity_type="devices",
        entity_id=device.id,
        new_value={"device_uid": device.device_uid, "device_type": device.device_type.type_name},
        ip_address=request.client.host if request.client else None,
    )
    return _to_device_out(device)


@router.get("/devices/{device_id}", response_model=DeviceOut)
def get_device(
    device_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    device = device_service.get_device(db, device_id)
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")
    return _to_device_out(device)


@router.patch("/devices/{device_id}", response_model=DeviceOut)
def update_device(
    device_id: int,
    body: DeviceUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("devices.read")),
):
    updates = body.model_dump(exclude_unset=True)
    before = device_service.get_device(db, device_id)
    old_status = before.status if before else None

    device = device_service.update_device(
        db,
        device_id=device_id,
        updates=updates,
        actor_permissions=ctx.permissions,
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="QUARANTINE_DEVICE" if "status" in updates else "UPDATE_DEVICE",
        entity_type="devices",
        entity_id=device_id,
        old_value={"status": old_status} if "status" in updates else None,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return _to_device_out(device)
