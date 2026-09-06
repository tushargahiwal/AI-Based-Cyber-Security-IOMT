from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Boolean, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class BlocklistEntry(Base):
    __tablename__ = "blocklist"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    entry_type: Mapped[str] = mapped_column(
        Enum("ip", "mac", "mqtt_client", name="blocklist_entry_type"), nullable=False
    )
    value: Mapped[str] = mapped_column(String(100), nullable=False)
    reason: Mapped[str | None] = mapped_column(String(255))
    alert_id: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("alerts.id"))
    added_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    expires_at: Mapped[datetime | None] = mapped_column(DateTime)
    is_active: Mapped[bool] = mapped_column(Boolean, default=True, nullable=False)
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())
