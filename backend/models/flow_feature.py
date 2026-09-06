from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    JSON,
    TIMESTAMP,
    BigInteger,
    Boolean,
    ForeignKey,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class FlowFeature(Base):
    __tablename__ = "flow_features"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("network_flows.id"), unique=True, nullable=False)
    feature_vector: Mapped[list] = mapped_column(JSON, nullable=False)
    feature_set_version: Mapped[str] = mapped_column(String(20), nullable=False)
    flow_bytes_per_sec: Mapped[float | None] = mapped_column(DECIMAL(14, 3))
    flow_packets_per_sec: Mapped[float | None] = mapped_column(DECIMAL(14, 3))
    syn_ratio: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    rst_ratio: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    down_up_ratio: Mapped[float | None] = mapped_column(DECIMAL(10, 4))
    pkt_len_mean: Mapped[float | None] = mapped_column(DECIMAL(10, 3))
    pkt_len_std: Mapped[float | None] = mapped_column(DECIMAL(10, 3))
    iat_mean_ms: Mapped[float | None] = mapped_column(DECIMAL(12, 3))
    ttl_deviation: Mapped[int | None] = mapped_column(SmallInteger)
    payload_entropy: Mapped[float | None] = mapped_column(DECIMAL(6, 4))
    mqtt_connect_ratio: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    device_profile_deviation: Mapped[float | None] = mapped_column(DECIMAL(10, 4))
    arp_binding_violation: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())
