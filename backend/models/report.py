from datetime import datetime

from sqlalchemy import JSON, TIMESTAMP, BigInteger, DateTime, Enum, ForeignKey, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class Report(Base):
    __tablename__ = "reports"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    report_type: Mapped[str] = mapped_column(
        Enum("daily", "weekly", "incident", "compliance", "custom", "patient", "device", "ward",
             name="report_type"),
        nullable=False,
    )
    title: Mapped[str | None] = mapped_column(String(200))
    period_start: Mapped[datetime | None] = mapped_column(DateTime)
    period_end: Mapped[datetime | None] = mapped_column(DateTime)
    filters: Mapped[dict | None] = mapped_column(JSON)
    summary_stats: Mapped[dict | None] = mapped_column(JSON)
    file_path: Mapped[str | None] = mapped_column(String(255))
    generated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())

    author = relationship("User")
