from datetime import datetime

from sqlalchemy import DECIMAL, JSON, BigInteger, DateTime, ForeignKey, Integer, SmallInteger
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class DeviceProfile(Base):
    __tablename__ = "device_profiles"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("devices.id"), unique=True, nullable=False
    )
    baseline_vector: Mapped[list] = mapped_column(JSON, nullable=False)
    baseline_std: Mapped[list] = mapped_column(JSON, nullable=False)
    typical_ports: Mapped[list | None] = mapped_column(JSON)
    typical_peers: Mapped[list | None] = mapped_column(JSON)
    modal_ttl: Mapped[int | None] = mapped_column(SmallInteger)
    avg_pkts_per_sec: Mapped[float | None] = mapped_column(DECIMAL(10, 3))
    active_hours: Mapped[list | None] = mapped_column(JSON)
    samples_used: Mapped[int | None] = mapped_column(Integer)
    profile_version: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    last_recomputed_at: Mapped[datetime | None] = mapped_column(DateTime)

    device = relationship("Device")
