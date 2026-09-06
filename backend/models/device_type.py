from sqlalchemy import DECIMAL, JSON, Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class DeviceType(Base):
    __tablename__ = "device_types"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    type_name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    category: Mapped[str] = mapped_column(
        Enum("sensor", "actuator", "gateway", "hybrid", name="device_type_category"),
        nullable=False,
    )
    is_life_critical: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    default_protocols: Mapped[list | None] = mapped_column(JSON)
    expected_data_rate_kbps: Mapped[float | None] = mapped_column(DECIMAL(8, 2))
