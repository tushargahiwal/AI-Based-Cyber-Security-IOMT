from datetime import datetime

from sqlalchemy import BIGINT, TIMESTAMP, BigInteger, CHAR, DateTime, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class NetworkFlow(Base):
    __tablename__ = "network_flows"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flow_uid: Mapped[str] = mapped_column(CHAR(36), unique=True, nullable=False)
    device_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("devices.id"))
    src_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    dst_ip: Mapped[str] = mapped_column(String(45), nullable=False)
    src_port: Mapped[int | None] = mapped_column(Integer)
    dst_port: Mapped[int | None] = mapped_column(Integer)
    protocol: Mapped[str] = mapped_column(
        Enum("TCP", "UDP", "ICMP", "MQTT", "HTTP", "BLE", "OTHER", name="flow_protocol"), nullable=False
    )
    src_mac: Mapped[str | None] = mapped_column(String(17))
    dst_mac: Mapped[str | None] = mapped_column(String(17))
    flow_start: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    flow_end: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    duration_ms: Mapped[int | None] = mapped_column(Integer)
    total_fwd_packets: Mapped[int | None] = mapped_column(Integer, default=0)
    total_bwd_packets: Mapped[int | None] = mapped_column(Integer, default=0)
    total_fwd_bytes: Mapped[int | None] = mapped_column(BIGINT, default=0)
    total_bwd_bytes: Mapped[int | None] = mapped_column(BIGINT, default=0)
    capture_source: Mapped[str] = mapped_column(
        Enum("live", "pcap", "dataset", "simulated", name="flow_capture_source"),
        default="live",
        nullable=False,
    )
    pcap_reference: Mapped[str | None] = mapped_column(String(255))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())

    device = relationship("Device")
