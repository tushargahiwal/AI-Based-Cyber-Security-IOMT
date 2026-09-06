from sqlalchemy import Enum, Integer, String
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Ward(Base):
    __tablename__ = "wards"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), nullable=False)
    floor: Mapped[str | None] = mapped_column(String(20))
    network_segment: Mapped[str | None] = mapped_column(String(50))
    criticality: Mapped[str] = mapped_column(
        Enum("low", "medium", "high", "critical", name="ward_criticality"),
        nullable=False,
        default="medium",
    )
