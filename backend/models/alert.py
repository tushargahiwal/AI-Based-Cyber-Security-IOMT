from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    TIMESTAMP,
    BigInteger,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    String,
    Text,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Alert(Base):
    __tablename__ = "alerts"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_uid: Mapped[str] = mapped_column(String(20), unique=True, nullable=False)
    detection_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("detections.id"), nullable=False)
    device_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("devices.id"))
    patient_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("patients.id"))
    attack_type_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("attack_types.id"))
    title: Mapped[str] = mapped_column(String(200), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    severity: Mapped[str] = mapped_column(
        Enum("info", "low", "medium", "high", "critical", name="alert_severity"), nullable=False
    )
    risk_score: Mapped[float | None] = mapped_column(DECIMAL(5, 2))
    status: Mapped[str] = mapped_column(
        Enum("new", "acknowledged", "investigating", "resolved", "false_positive", name="alert_status"),
        default="new",
        nullable=False,
    )
    assigned_to: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    correlated_alert_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("alerts.id"))
    occurrence_count: Mapped[int] = mapped_column(Integer, default=1, nullable=False)
    first_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    last_seen_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)
    acknowledged_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolved_at: Mapped[datetime | None] = mapped_column(DateTime)
    resolution_notes: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )

    detection = relationship("Detection")
    device = relationship("Device")
    patient = relationship("Patient")
    attack_type = relationship("AttackType")
    assignee = relationship("User", foreign_keys=[assigned_to])
