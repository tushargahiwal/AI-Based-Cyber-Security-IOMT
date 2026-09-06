from datetime import datetime

from sqlalchemy import JSON, BigInteger, DateTime, Enum, ForeignKey, Integer, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class TrainingRun(Base):
    __tablename__ = "training_runs"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    model_id: Mapped[int] = mapped_column(Integer, ForeignKey("ml_models.id"), nullable=False)
    dataset_id: Mapped[int | None] = mapped_column(Integer, ForeignKey("datasets.id"))
    run_uid: Mapped[str] = mapped_column(String(36), unique=True, nullable=False)
    train_size: Mapped[int | None] = mapped_column(Integer)
    val_size: Mapped[int | None] = mapped_column(Integer)
    test_size: Mapped[int | None] = mapped_column(Integer)
    resampling_method: Mapped[str | None] = mapped_column(String(50))
    epochs: Mapped[int | None] = mapped_column(Integer)
    batch_size: Mapped[int | None] = mapped_column(Integer)
    duration_seconds: Mapped[int | None] = mapped_column(Integer)
    hardware: Mapped[str | None] = mapped_column(String(100))
    status: Mapped[str] = mapped_column(
        Enum("running", "completed", "failed", name="training_run_status"),
        default="running",
        nullable=False,
    )
    loss_curve: Mapped[dict | None] = mapped_column(JSON)
    notes: Mapped[str | None] = mapped_column(Text)
    started_at: Mapped[datetime | None] = mapped_column(DateTime)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime)

    model = relationship("MlModel")
    dataset = relationship("Dataset")
    metrics = relationship("ModelMetric", back_populates="training_run")
