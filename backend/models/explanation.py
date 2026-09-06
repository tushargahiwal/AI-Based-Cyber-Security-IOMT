from datetime import datetime

from sqlalchemy import DECIMAL, JSON, TIMESTAMP, BigInteger, Enum, ForeignKey, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Explanation(Base):
    __tablename__ = "explanations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    # One explanation per detection: it explains a fixed model output, so there
    # is nothing to recompute unless the detection itself changes.
    detection_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("detections.id"), unique=True, nullable=False
    )
    method: Mapped[str] = mapped_column(
        Enum("SHAP", "LIME", name="explanation_method"), nullable=False, default="SHAP"
    )
    base_value: Mapped[float | None] = mapped_column(DECIMAL(12, 8))
    top_features: Mapped[list] = mapped_column(JSON, nullable=False)
    narrative: Mapped[str | None] = mapped_column(Text)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())

    detection = relationship("Detection")
