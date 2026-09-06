from datetime import datetime

from sqlalchemy import (
    DECIMAL,
    JSON,
    TIMESTAMP,
    BigInteger,
    Boolean,
    DateTime,
    Enum,
    ForeignKey,
    Integer,
    SmallInteger,
    String,
    func,
)
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class MlModel(Base):
    __tablename__ = "ml_models"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, autoincrement=True)
    model_code: Mapped[str] = mapped_column(String(40), unique=True, nullable=False)
    display_name: Mapped[str | None] = mapped_column(String(100))
    stage: Mapped[int | None] = mapped_column(SmallInteger)
    algorithm: Mapped[str | None] = mapped_column(String(60))
    task_type: Mapped[str | None] = mapped_column(
        Enum("binary", "multiclass", "anomaly", "regression", "meta", name="ml_model_task_type")
    )
    version: Mapped[str] = mapped_column(String(20), nullable=False)
    artifact_path: Mapped[str] = mapped_column(String(255), nullable=False)
    scaler_path: Mapped[str | None] = mapped_column(String(255))
    feature_set_version: Mapped[str | None] = mapped_column(String(20))
    hyperparameters: Mapped[dict | None] = mapped_column(JSON)
    input_dim: Mapped[int | None] = mapped_column(SmallInteger)
    output_classes: Mapped[list | None] = mapped_column(JSON)
    threshold: Mapped[float | None] = mapped_column(DECIMAL(6, 4))
    is_active: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    trained_at: Mapped[datetime | None] = mapped_column(DateTime)
    trained_by: Mapped[int | None] = mapped_column(BigInteger, ForeignKey("users.id"))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())

    trained_by_user = relationship("User")
