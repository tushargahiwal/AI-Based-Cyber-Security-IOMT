from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    ForeignKey,
    SmallInteger,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class VitalReading(Base):
    __tablename__ = "vital_readings"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    device_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("devices.id"), nullable=False)
    patient_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("patients.id"))
    recorded_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    heart_rate: Mapped[int | None] = mapped_column(SmallInteger)
    spo2: Mapped[int | None] = mapped_column(SmallInteger)
    systolic_bp: Mapped[int | None] = mapped_column(SmallInteger)
    diastolic_bp: Mapped[int | None] = mapped_column(SmallInteger)
    body_temp: Mapped[float | None] = mapped_column(DECIMAL(4, 2))
    respiration_rate: Mapped[int | None] = mapped_column(SmallInteger)
    raw_payload: Mapped[dict | None] = mapped_column(JSON)

    # Stage 4 output — set at ingest once this device has WINDOW prior readings.
    is_plausible: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    predicted_values: Mapped[dict | None] = mapped_column(JSON)
    residual_zscore: Mapped[float | None] = mapped_column(DECIMAL(6, 3))
    injection_suspected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    device = relationship("Device")
    patient = relationship("Patient")
