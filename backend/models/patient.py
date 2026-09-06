from datetime import datetime

from sqlalchemy import BigInteger, DateTime, Enum, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Patient(Base):
    __tablename__ = "patients"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    patient_code: Mapped[str] = mapped_column(String(32), unique=True, nullable=False)
    age_band: Mapped[str | None] = mapped_column(String(16))
    sex: Mapped[str | None] = mapped_column(Enum("M", "F", "O", "U", name="patient_sex"))
    ward_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("wards.id"))
    admitted_at: Mapped[datetime | None] = mapped_column(DateTime)
    discharged_at: Mapped[datetime | None] = mapped_column(DateTime)
    baseline_hr_min: Mapped[int | None] = mapped_column(SmallInteger)
    baseline_hr_max: Mapped[int | None] = mapped_column(SmallInteger)
    baseline_spo2_min: Mapped[int | None] = mapped_column(SmallInteger)
    notes: Mapped[str | None] = mapped_column(String(255))

    ward = relationship("Ward")
