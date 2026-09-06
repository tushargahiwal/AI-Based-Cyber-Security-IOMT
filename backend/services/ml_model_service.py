from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.feature_importance import FeatureImportance
from models.ml_model import MlModel
from models.model_metric import ModelMetric
from models.training_run import TrainingRun


def list_models(db: Session, *, stage: int | None = None, task_type: str | None = None,
                 is_active: bool | None = None) -> list[MlModel]:
    query = db.query(MlModel)
    if stage is not None:
        query = query.filter(MlModel.stage == stage)
    if task_type:
        query = query.filter(MlModel.task_type == task_type)
    if is_active is not None:
        query = query.filter(MlModel.is_active == is_active)
    return query.order_by(MlModel.stage, MlModel.model_code).all()


def get_model(db: Session, model_id: int) -> MlModel | None:
    return db.query(MlModel).filter(MlModel.id == model_id).first()


def register_model(db: Session, *, data: dict, actor_user_id: int) -> MlModel:
    model = MlModel(**data, trained_by=actor_user_id, trained_at=datetime.utcnow())
    db.add(model)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "model_code already exists")
    db.refresh(model)
    return model


def update_model(db: Session, *, model_id: int, updates: dict) -> MlModel:
    model = db.query(MlModel).filter(MlModel.id == model_id).first()
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model not found")
    for field, value in updates.items():
        setattr(model, field, value)
    db.commit()
    db.refresh(model)
    return model


def activate_model(db: Session, *, model_id: int) -> MlModel:
    """Activates this model and deactivates every other model in the same
    pipeline stage — schema comment: 'only one active per stage'."""
    model = db.query(MlModel).filter(MlModel.id == model_id).first()
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model not found")

    if model.stage is not None:
        db.query(MlModel).filter(
            MlModel.stage == model.stage, MlModel.id != model.id
        ).update({"is_active": False})

    model.is_active = True
    db.commit()
    db.refresh(model)
    return model


def get_evaluation(db: Session, model_id: int) -> dict:
    """Every training run for a model, its metrics, and its feature importances.

    Assembled here rather than through lazy relationships so the router does one
    call and the response shape is fixed in one place.
    """
    runs = (
        db.query(TrainingRun)
        .filter(TrainingRun.model_id == model_id)
        # MySQL has no NULLS LAST; sorting on the is-null flag first is portable
        # and keeps runs that never finished at the bottom.
        .order_by(TrainingRun.finished_at.is_(None), TrainingRun.finished_at.desc(),
                  TrainingRun.id.desc())
        .all()
    )
    metrics_by_run: dict[int, list[ModelMetric]] = {}
    if runs:
        rows = (
            db.query(ModelMetric)
            .filter(ModelMetric.training_run_id.in_([r.id for r in runs]))
            .order_by(ModelMetric.split, ModelMetric.class_label)
            .all()
        )
        for row in rows:
            metrics_by_run.setdefault(row.training_run_id, []).append(row)

    importances = (
        db.query(FeatureImportance)
        .filter(FeatureImportance.model_id == model_id)
        .order_by(FeatureImportance.rank)
        .all()
    )
    return {"runs": runs, "metrics_by_run": metrics_by_run, "importances": importances}
