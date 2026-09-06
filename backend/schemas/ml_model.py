from datetime import datetime
from typing import Optional

from pydantic import BaseModel, Field

TASK_TYPE_PATTERN = "^(binary|multiclass|anomaly|regression|meta)$"


class MlModelCreateRequest(BaseModel):
    model_code: str = Field(min_length=2, max_length=40)
    display_name: Optional[str] = Field(default=None, max_length=100)
    stage: Optional[int] = Field(default=None, ge=1, le=5)
    algorithm: Optional[str] = Field(default=None, max_length=60)
    task_type: Optional[str] = Field(default=None, pattern=TASK_TYPE_PATTERN)
    version: str = Field(min_length=1, max_length=20)
    artifact_path: str = Field(min_length=1, max_length=255)
    scaler_path: Optional[str] = Field(default=None, max_length=255)
    feature_set_version: Optional[str] = Field(default=None, max_length=20)
    hyperparameters: Optional[dict] = None
    input_dim: Optional[int] = Field(default=None, ge=0)
    output_classes: Optional[list] = None
    threshold: Optional[float] = Field(default=None, ge=0, le=1)


class MlModelUpdateRequest(BaseModel):
    display_name: Optional[str] = Field(default=None, max_length=100)
    stage: Optional[int] = Field(default=None, ge=1, le=5)
    algorithm: Optional[str] = Field(default=None, max_length=60)
    task_type: Optional[str] = Field(default=None, pattern=TASK_TYPE_PATTERN)
    version: Optional[str] = Field(default=None, min_length=1, max_length=20)
    artifact_path: Optional[str] = Field(default=None, min_length=1, max_length=255)
    scaler_path: Optional[str] = Field(default=None, max_length=255)
    feature_set_version: Optional[str] = Field(default=None, max_length=20)
    hyperparameters: Optional[dict] = None
    input_dim: Optional[int] = Field(default=None, ge=0)
    output_classes: Optional[list] = None
    threshold: Optional[float] = Field(default=None, ge=0, le=1)


class ModelMetricOut(BaseModel):
    split: str
    class_label: Optional[str] = None
    accuracy: Optional[float] = None
    precision: Optional[float] = None
    recall: Optional[float] = None
    f1_score: Optional[float] = None
    roc_auc: Optional[float] = None
    false_positive_rate: Optional[float] = None
    support: Optional[int] = None
    confusion_matrix: Optional[list] = None
    avg_inference_ms: Optional[float] = None


class TrainingRunOut(BaseModel):
    id: int
    run_uid: str
    dataset_name: Optional[str] = None
    resampling_method: Optional[str] = None
    epochs: Optional[int] = None
    duration_seconds: Optional[int] = None
    status: str
    notes: Optional[str] = None
    finished_at: Optional[datetime] = None
    metrics: list[ModelMetricOut] = []


class FeatureImportanceOut(BaseModel):
    feature_name: str
    importance_gain: Optional[float] = None
    shap_mean_abs: Optional[float] = None
    rank: Optional[int] = None


class ModelEvaluationOut(BaseModel):
    model_id: int
    model_code: str
    training_runs: list[TrainingRunOut] = []
    feature_importances: list[FeatureImportanceOut] = []


class MlModelOut(BaseModel):
    id: int
    model_code: str
    display_name: Optional[str] = None
    stage: Optional[int] = None
    algorithm: Optional[str] = None
    task_type: Optional[str] = None
    version: str
    artifact_path: str
    scaler_path: Optional[str] = None
    feature_set_version: Optional[str] = None
    hyperparameters: Optional[dict] = None
    input_dim: Optional[int] = None
    output_classes: Optional[list] = None
    threshold: Optional[float] = None
    is_active: bool
    trained_at: Optional[datetime] = None
    trained_by: Optional[int] = None
    trained_by_username: Optional[str] = None
    created_at: Optional[datetime] = None
