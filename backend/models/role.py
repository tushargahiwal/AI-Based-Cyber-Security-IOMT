from sqlalchemy import JSON, TIMESTAMP, SmallInteger, String, func
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Role(Base):
    __tablename__ = "roles"

    id: Mapped[int] = mapped_column(SmallInteger, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(50), unique=True, nullable=False)
    description: Mapped[str | None] = mapped_column(String(255))
    permissions: Mapped[list] = mapped_column(JSON, nullable=False)
    created_at = mapped_column(TIMESTAMP, server_default=func.current_timestamp())
