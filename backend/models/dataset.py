from sqlalchemy import DECIMAL, BigInteger, Integer, SmallInteger, String, Text
from sqlalchemy.orm import Mapped, mapped_column

from database import Base


class Dataset(Base):
    __tablename__ = "datasets"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    name: Mapped[str] = mapped_column(String(100), unique=True, nullable=False)
    version: Mapped[str | None] = mapped_column(String(20))
    source_url: Mapped[str | None] = mapped_column(String(255))
    total_records: Mapped[int | None] = mapped_column(BigInteger)
    num_features: Mapped[int | None] = mapped_column(SmallInteger)
    num_classes: Mapped[int | None] = mapped_column(SmallInteger)
    benign_ratio: Mapped[float | None] = mapped_column(DECIMAL(5, 4))
    citation: Mapped[str | None] = mapped_column(Text)
    notes: Mapped[str | None] = mapped_column(Text)
