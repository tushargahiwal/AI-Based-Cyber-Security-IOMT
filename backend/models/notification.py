from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Notification(Base):
    __tablename__ = "notifications"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    alert_id: Mapped[int] = mapped_column(BigInteger, ForeignKey("alerts.id"), nullable=False)
    channel: Mapped[str] = mapped_column(
        Enum("email", "sms", "telegram", "webhook", "websocket", name="notification_channel"),
        nullable=False,
    )
    recipient: Mapped[str | None] = mapped_column(String(150))
    payload: Mapped[dict | None] = mapped_column(JSON)
    status: Mapped[str] = mapped_column(
        Enum("pending", "sent", "failed", name="notification_status"),
        default="pending",
        nullable=False,
    )
    retry_count: Mapped[int] = mapped_column(SmallInteger, default=0, nullable=False)
    error_message: Mapped[str | None] = mapped_column(String(255))
    sent_at: Mapped[datetime | None] = mapped_column(DateTime)

    alert = relationship("Alert")
