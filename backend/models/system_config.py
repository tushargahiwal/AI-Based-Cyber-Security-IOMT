from datetime import datetime

from sqlalchemy import TIMESTAMP, BigInteger, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class SystemConfig(Base):
    __tablename__ = "system_config"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    config_key: Mapped[str] = mapped_column(String(80), unique=True, nullable=False)
    config_value: Mapped[str | None] = mapped_column(String(255))
    value_type: Mapped[str] = mapped_column(
        Enum("string", "int", "float", "bool", "json", name="config_value_type"), nullable=False
    )
    description: Mapped[str | None] = mapped_column(String(255))
    updated_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    updated_at: Mapped[datetime] = mapped_column(
        TIMESTAMP, server_default=func.current_timestamp(), onupdate=func.current_timestamp()
    )
