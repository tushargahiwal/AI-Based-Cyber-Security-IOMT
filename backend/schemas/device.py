from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field


class DeviceTypeOut(BaseModel):
    id: int
    type_name: str
    category: str
    is_life_critical: bool
    default_protocols: Optional[list] = None
    expected_data_rate_kbps: Optional[float] = None

    model_config = {"from_attributes": True}


class WardOut(BaseModel):
    id: int
    name: str
    floor: Optional[str] = None
    network_segment: Optional[str] = None
    criticality: str

    model_config = {"from_attributes": True}


class DeviceCreateRequest(BaseModel):
    device_uid: str = Field(min_length=2, max_length=64)
    device_type: str = Field(description="device_types.type_name, e.g. 'Patient Monitor'")
    ward: Optional[str] = Field(default=None, description="wards.name, e.g. 'ICU-1'")
    manufacturer: Optional[str] = Field(default=None, max_length=100)
    model_number: Optional[str] = Field(default=None, max_length=100)
    firmware_version: Optional[str] = Field(default=None, max_length=50)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    mac_address: Optional[str] = Field(default=None, max_length=17)
    mqtt_client_id: Optional[str] = Field(default=None, max_length=100)


class DeviceUpdateRequest(BaseModel):
    device_type: Optional[str] = None
    ward: Optional[str] = None
    manufacturer: Optional[str] = Field(default=None, max_length=100)
    model_number: Optional[str] = Field(default=None, max_length=100)
    firmware_version: Optional[str] = Field(default=None, max_length=50)
    ip_address: Optional[str] = Field(default=None, max_length=45)
    mac_address: Optional[str] = Field(default=None, max_length=17)
    mqtt_client_id: Optional[str] = Field(default=None, max_length=100)
    status: Optional[str] = Field(
        default=None, pattern="^(online|offline|quarantined|maintenance)$"
    )


class DeviceOut(BaseModel):
    id: int
    device_uid: str
    device_type: DeviceTypeOut
    ward: Optional[WardOut] = None
    manufacturer: Optional[str] = None
    model_number: Optional[str] = None
    firmware_version: Optional[str] = None
    ip_address: Optional[str] = None
    mac_address: Optional[str] = None
    mqtt_client_id: Optional[str] = None
    status: str
    trust_score: float
    last_seen_at: Optional[datetime] = None
    created_at: Optional[datetime] = None


class DeviceListResponse(BaseModel):
    items: list[DeviceOut]
    total: int
    page: int
    size: int
