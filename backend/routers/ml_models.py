from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, require_permission
from schemas.ml_model import (
    FeatureImportanceOut,
    MlModelCreateRequest,
    MlModelOut,
    MlModelUpdateRequest,
    ModelEvaluationOut,
    ModelMetricOut,
    TrainingRunOut,
)
from services import audit_service, ml_model_service

router = APIRouter(prefix="/api/v1/models", tags=["models"])


def _to_out(model) -> MlModelOut:
    return MlModelOut(
        id=model.id,
        model_code=model.model_code,
        display_name=model.display_name,
        stage=model.stage,
        algorithm=model.algorithm,
        task_type=model.task_type,
        version=model.version,
        artifact_path=model.artifact_path,
        scaler_path=model.scaler_path,
        feature_set_version=model.feature_set_version,
        hyperparameters=model.hyperparameters,
        input_dim=model.input_dim,
        output_classes=model.output_classes,
        threshold=float(model.threshold) if model.threshold is not None else None,
        is_active=model.is_active,
        trained_at=model.trained_at,
        trained_by=model.trained_by,
        trained_by_username=model.trained_by_user.username if model.trained_by_user else None,
        created_at=model.created_at,
    )


@router.get("", response_model=list[MlModelOut])
def list_models(
    stage: int | None = Query(default=None, ge=1, le=5),
    task_type: str | None = Query(default=None),
    is_active: bool | None = Query(default=None),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("models.read")),
):
    return [
        _to_out(m)
        for m in ml_model_service.list_models(db, stage=stage, task_type=task_type, is_active=is_active)
    ]


@router.post("", response_model=MlModelOut, status_code=status.HTTP_201_CREATED)
def register_model(
    body: MlModelCreateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("models.retrain")),
):
    model = ml_model_service.register_model(db, data=body.model_dump(), actor_user_id=ctx.user.id)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="REGISTER_ML_MODEL",
        entity_type="ml_models",
        entity_id=model.id,
        new_value={"model_code": model.model_code, "version": model.version, "stage": model.stage},
        ip_address=request.client.host if request.client else None,
    )
    return _to_out(model)


@router.get("/{model_id}", response_model=MlModelOut)
def get_model(
    model_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("models.read")),
):
    model = ml_model_service.get_model(db, model_id)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model not found")
    return _to_out(model)


@router.patch("/{model_id}", response_model=MlModelOut)
def update_model(
    model_id: int,
    body: MlModelUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("models.retrain")),
):
    updates = body.model_dump(exclude_unset=True)
    model = ml_model_service.update_model(db, model_id=model_id, updates=updates)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="UPDATE_ML_MODEL",
        entity_type="ml_models",
        entity_id=model_id,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return _to_out(model)


@router.post("/{model_id}/activate", response_model=MlModelOut)
def activate_model(
    model_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("models.activate")),
):
    model = ml_model_service.activate_model(db, model_id=model_id)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="ACTIVATE_ML_MODEL",
        entity_type="ml_models",
        entity_id=model_id,
        new_value={"model_code": model.model_code, "stage": model.stage},
        ip_address=request.client.host if request.client else None,
    )
    return _to_out(model)


@router.get("/{model_id}/evaluation", response_model=ModelEvaluationOut)
def get_model_evaluation(
    model_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("models.read")),
):
    """Measured results for a model — what it actually scores, not what it is.

    Populated by backend/register_models.py from the ml/ results files, so a
    model shows numbers here only once it has genuinely been evaluated.
    """
    model = ml_model_service.get_model(db, model_id)
    if model is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "model not found")

    data = ml_model_service.get_evaluation(db, model_id)
    return ModelEvaluationOut(
        model_id=model.id,
        model_code=model.model_code,
        training_runs=[
            TrainingRunOut(
                id=run.id,
                run_uid=run.run_uid,
                dataset_name=run.dataset.name if run.dataset else None,
                resampling_method=run.resampling_method,
                epochs=run.epochs,
                duration_seconds=run.duration_seconds,
                status=run.status,
                notes=run.notes,
                finished_at=run.finished_at,
                metrics=[
                    ModelMetricOut(
                        split=m.split,
                        class_label=m.class_label,
                        accuracy=float(m.accuracy) if m.accuracy is not None else None,
                        precision=float(m.precision) if m.precision is not None else None,
                        recall=float(m.recall) if m.recall is not None else None,
                        f1_score=float(m.f1_score) if m.f1_score is not None else None,
                        roc_auc=float(m.roc_auc) if m.roc_auc is not None else None,
                        false_positive_rate=(
                            float(m.false_positive_rate) if m.false_positive_rate is not None else None
                        ),
                        support=m.support,
                        confusion_matrix=m.confusion_matrix,
                        avg_inference_ms=(
                            float(m.avg_inference_ms) if m.avg_inference_ms is not None else None
                        ),
                    )
                    for m in data["metrics_by_run"].get(run.id, [])
                ],
            )
            for run in data["runs"]
        ],
        feature_importances=[
            FeatureImportanceOut(
                feature_name=f.feature_name,
                importance_gain=float(f.importance_gain) if f.importance_gain is not None else None,
                shap_mean_abs=float(f.shap_mean_abs) if f.shap_mean_abs is not None else None,
                rank=f.rank,
            )
            for f in data["importances"]
        ],
    )
