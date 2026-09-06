from datetime import datetime

from sqlalchemy import DECIMAL, TIMESTAMP, BigInteger, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Device(Base):
    __tablename__ = "devices"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_uid: Mapped[str] = mapped_column(String(64), unique=True, nullable=False)
    device_type_id: Mapped[int] = mapped_column(Integer, ForeignKey("device_types.id"), nullable=False)
    ward_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("wards.id"))
    manufacturer: Mapped[str | None] = mapped_column(String(100))
    model_number: Mapped[str | None] = mapped_column(String(100))
    firmware_version: Mapped[str | None] = mapped_column(String(50))
    ip_address: Mapped[str | None] = mapped_column(String(45))
    mac_address: Mapped[str | None] = mapped_column(String(17), unique=True)
    registered_mac_ip_binding: Mapped[str | None] = mapped_column(String(64))
    mqtt_client_id: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        Enum("online", "offline", "quarantined", "maintenance", name="device_status"),
        nullable=False,
        default="offline",
    )
    trust_score: Mapped[float] = mapped_column(DECIMAL(5, 2), default=100.00, nullable=False)
    last_seen_at: Mapped[datetime | None] = mapped_column(DateTime)
    created_at = mapped_column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at = mapped_column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    device_type = relationship("DeviceType")
    ward = relationship("Ward")
