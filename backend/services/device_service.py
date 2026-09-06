from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.device import Device
from models.device_type import DeviceType
from models.ward import Ward

# Changing anything other than 'status' requires devices.write.
# 'status' alone (quarantine/unquarantine/maintenance) only requires devices.quarantine.
STATUS_ONLY_FIELD = {"status"}


def list_device_types(db: Session) -> list[DeviceType]:
    return db.query(DeviceType).order_by(DeviceType.type_name).all()


def list_wards(db: Session) -> list[Ward]:
    return db.query(Ward).order_by(Ward.name).all()


def _resolve_device_type(db: Session, type_name: str) -> DeviceType:
    device_type = db.query(DeviceType).filter(DeviceType.type_name == type_name).first()
    if device_type is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown device_type '{type_name}'")
    return device_type


def _resolve_ward(db: Session, ward_name: str | None) -> Ward | None:
    if ward_name is None:
        return None
    ward = db.query(Ward).filter(Ward.name == ward_name).first()
    if ward is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown ward '{ward_name}'")
    return ward


def list_devices(
    db: Session,
    *,
    page: int,
    size: int,
    ward: str | None = None,
    device_type: str | None = None,
    status_filter: str | None = None,
):
    query = db.query(Device)
    if ward:
        query = query.join(Ward).filter(Ward.name == ward)
    if device_type:
        query = query.join(DeviceType).filter(DeviceType.type_name == device_type)
    if status_filter:
        query = query.filter(Device.status == status_filter)

    query = query.order_by(Device.id)
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total


def get_device(db: Session, device_id: int) -> Device | None:
    return db.query(Device).filter(Device.id == device_id).first()


def register_device(db: Session, *, device_uid: str, device_type_name: str, ward_name: str | None,
                     manufacturer: str | None, model_number: str | None, firmware_version: str | None,
                     ip_address: str | None, mac_address: str | None, mqtt_client_id: str | None) -> Device:
    device_type = _resolve_device_type(db, device_type_name)
    ward = _resolve_ward(db, ward_name)

    device = Device(
        device_uid=device_uid,
        device_type_id=device_type.id,
        ward_id=ward.id if ward else None,
        manufacturer=manufacturer,
        model_number=model_number,
        firmware_version=firmware_version,
        ip_address=ip_address,
        mac_address=mac_address,
        registered_mac_ip_binding=f"{mac_address}|{ip_address}" if mac_address and ip_address else None,
        mqtt_client_id=mqtt_client_id,
    )
    db.add(device)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "device_uid or mac_address already registered")
    db.refresh(device)
    return device


def update_device(db: Session, *, device_id: int, updates: dict, actor_permissions: list) -> Device:
    is_admin_write = "*" in actor_permissions or "devices.write" in actor_permissions
    can_quarantine = is_admin_write or "devices.quarantine" in actor_permissions

    non_status_fields = updates.keys() - STATUS_ONLY_FIELD
    if non_status_fields and not is_admin_write:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "missing permission: devices.write")
    if "status" in updates and not can_quarantine:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "missing permission: devices.quarantine")

    device = db.query(Device).filter(Device.id == device_id).first()
    if device is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "device not found")

    if "device_type" in updates:
        device.device_type_id = _resolve_device_type(db, updates["device_type"]).id
    if "ward" in updates:
        ward = _resolve_ward(db, updates["ward"])
        device.ward_id = ward.id if ward else None

    for field in ("manufacturer", "model_number", "firmware_version", "ip_address",
                  "mac_address", "mqtt_client_id", "status"):
        if field in updates:
            setattr(device, field, updates[field])

    if "mac_address" in updates or "ip_address" in updates:
        if device.mac_address and device.ip_address:
            device.registered_mac_ip_binding = f"{device.mac_address}|{device.ip_address}"

    if "status" in updates and updates["status"] == "online":
        device.last_seen_at = datetime.utcnow()

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "device_uid or mac_address already in use")
    db.refresh(device)
    return device
