from datetime import datetime

from sqlalchemy import DECIMAL, JSON, TIMESTAMP, BigInteger, Enum, ForeignKey, Integer, String, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from database import Base


class ModelMetric(Base):
    __tablename__ = "model_metrics"

    id: Mapped[int] = mapped_column(BigInteger, primary_key=True, autoincrement=True)
    training_run_id: Mapped[int] = mapped_column(
        BigInteger, ForeignKey("training_runs.id"), nullable=False
    )
    split: Mapped[str] = mapped_column(
        Enum("train", "validation", "test", "cross_dataset", name="model_metric_split"),
        nullable=False,
    )
    # NULL means the row is the overall score; a value means it is per-class.
    class_label: Mapped[str | None] = mapped_column(String(50))
    accuracy: Mapped[float | None] = mapped_column(DECIMAL(7, 6))
    # precision and recall are reserved words in MySQL, which is why schema.sql
    # backquotes them; naming the column explicitly keeps the mapping honest.
    precision: Mapped[float | None] = mapped_column("precision", DECIMAL(7, 6))
    recall: Mapped[float | None] = mapped_column("recall", DECIMAL(7, 6))
    f1_score: Mapped[float | None] = mapped_column(DECIMAL(7, 6))
    roc_auc: Mapped[float | None] = mapped_column(DECIMAL(7, 6))
    pr_auc: Mapped[float | None] = mapped_column(DECIMAL(7, 6))
    false_positive_rate: Mapped[float | None] = mapped_column(DECIMAL(7, 6))
    false_negative_rate: Mapped[float | None] = mapped_column(DECIMAL(7, 6))
    support: Mapped[int | None] = mapped_column(Integer)
    confusion_matrix: Mapped[list | None] = mapped_column(JSON)
    avg_inference_ms: Mapped[float | None] = mapped_column(DECIMAL(8, 3))
    created_at: Mapped[datetime] = mapped_column(TIMESTAMP, server_default=func.current_timestamp())

    training_run = relationship("TrainingRun", back_populates="metrics")
