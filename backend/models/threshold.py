from sqlalchemy import DECIMAL, BigInteger, Boolean, Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Threshold(Base):
    __tablename__ = "thresholds"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    scope: Mapped[str] = mapped_column(
        Enum("global", "device_type", "device", "patient", name="threshold_scope"), nullable=False
    )
    scope_id: Mapped[int | None] = mapped_column(BigInteger)
    metric: Mapped[str] = mapped_column(String(50), nullable=False)
    min_value: Mapped[float | None] = mapped_column(DECIMAL(12, 4))
    max_value: Mapped[float | None] = mapped_column(DECIMAL(12, 4))
    max_delta_per_sec: Mapped[float | None] = mapped_column(DECIMAL(12, 4))
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
