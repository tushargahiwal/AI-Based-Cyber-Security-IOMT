from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    JSON,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Detection(Base):
    __tablename__ = "detections"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    flow_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("network_flows.id"), nullable=False)
    device_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("devices.id"))

    stage1_model_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ml_models.id"))
    stage1_label: Mapped[str] = mapped_column(Enum("benign", "malicious", name="detection_stage1_label"), nullable=False)
    stage1_probability: Mapped[float | None] = mapped_column(DECIMAL(6, 5))

    stage2_model_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ml_models.id"))
    stage2_attack_type_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("attack_types.id"))
    stage2_confidence: Mapped[float | None] = mapped_column(DECIMAL(6, 5))
    stage2_class_probs: Mapped[dict | None] = mapped_column(JSON)

    stage3_model_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("ml_models.id"))
    stage3_reconstruction_error: Mapped[float | None] = mapped_column(DECIMAL(12, 8))
    stage3_anomaly_score: Mapped[float | None] = mapped_column(DECIMAL(10, 6))
    stage3_is_anomaly: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)

    stage4_injection_suspected: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    stage4_max_zscore: Mapped[float | None] = mapped_column(DECIMAL(8, 4))

    final_verdict: Mapped[str] = mapped_column(
        Enum(
            "benign", "known_attack", "zero_day_suspect", "data_integrity", "uncertain",
            name="detection_final_verdict",
        ),
        nullable=False,
    )
    final_confidence: Mapped[float | None] = mapped_column(DECIMAL(6, 5))
    severity: Mapped[str] = mapped_column(
        Enum("info", "low", "medium", "high", "critical", name="detection_severity"),
        default="info",
        nullable=False,
    )
    inference_latency_ms: Mapped[float | None] = mapped_column(DECIMAL(8, 3))
    detected_at: Mapped[datetime] = mapped_column(DateTime, nullable=False)

    flow = relationship("NetworkFlow")
    device = relationship("Device")
    stage2_attack_type = relationship("AttackType", foreign_keys=[stage2_attack_type_id])
