from datetime import datetime

from sqlalchemy import BigInteger, Boolean, DateTime, Enum, ForeignKey, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class MitigationRecommendation(Base):
    __tablename__ = "mitigation_recommendations"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("alerts.id"), nullable=False)
    recommendation: Mapped[str] = mapped_column(String(255), nullable=False)
    action_type: Mapped[str | None] = mapped_column(
        Enum(
            "rate_limit", "isolate_source", "block_ip", "revoke_mqtt_client",
            "notify_biomed", "force_reauth", "manual_review",
            name="mitigation_action_type",
        )
    )
    target: Mapped[str | None] = mapped_column(String(100))
    is_automatable: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    requires_approval: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    applied: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    applied_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    applied_at: Mapped[datetime | None] = mapped_column(DateTime)
