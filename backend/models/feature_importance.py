from sqlalchemy import DECIMAL, BigInteger, ForeignKey, Integer, SmallInteger, String
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class FeatureImportance(Base):
    __tablename__ = "feature_importances"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ml_models.id"), nullable=False)
    feature_name: Mapped[str] = mapped_column(String(80), nullable=False)
    importance_gain: Mapped[float | None] = mapped_column(DECIMAL(10, 8))
    shap_mean_abs: Mapped[float | None] = mapped_column(DECIMAL(10, 8))
    rank: Mapped[int | None] = mapped_column("rank", SmallInteger)  # reserved word in MySQL 8

    model = relationship("MlModel")
