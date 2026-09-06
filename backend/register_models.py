"""Loads every trained model and its measured metrics into the registry.

The ml/ scripts write their numbers to models/*.json. Nothing read them back,
so ml_models held four rows with no metrics and training_runs, model_metrics and
feature_importances were empty — which is why the Models page could show a
registry but not a single result.

This closes that gap: it is the bridge between "we trained it" and "the system
knows what it scores". Idempotent — re-running after a retrain updates the rows
in place, matched by model_code and run_uid.

Run after training:
    cd backend && ./venv/Scripts/python.exe register_models.py
"""

import json
import uuid
from datetime import datetime
from pathlib import Path

import joblib
from sqlalchemy.orm import Session

from database import SessionLocal
from models.dataset import Dataset
from models.feature_importance import FeatureImportance
from models.ml_model import MlModel
from models.model_metric import ModelMetric
from models.training_run import TrainingRun

PROJECT_ROOT = Path(__file__).resolve().parent.parent
MODELS_DIR = PROJECT_ROOT / "models"

# model_code -> everything the registry needs that isn't in the results JSON.
# stage is None for models that are baselines or companions rather than a
# deployed pipeline stage; only one model per stage may be is_active.
REGISTRY = [
    {
        "model_code": "M1_RF_BINARY_WUSTL", "display_name": "M1 Random Forest (Stage 1)",
        "stage": 1, "algorithm": "RandomForest", "task_type": "binary",
        "artifact_path": "models/binary_rf_v1.pkl", "results": "binary_results.json",
        "results_key": "random_forest_M1", "active": True,
    },
    {
        "model_code": "M2_XGB_BINARY_WUSTL", "display_name": "M2 XGBoost (Stage 1 alternate)",
        "stage": None, "algorithm": "XGBoost", "task_type": "binary",
        "artifact_path": "models/binary_xgb_v1.pkl", "results": "stacking_results.json",
        "results_key": "xgboost_M2", "active": False,
    },
    {
        "model_code": "M5_IFOREST_WUSTL", "display_name": "M5 Isolation Forest (Stage 3 companion)",
        "stage": None, "algorithm": "IsolationForest", "task_type": "anomaly",
        "artifact_path": "models/isolation_forest_v1.pkl", "results": "novelty_results.json",
        "results_key": "isolation_forest_M5", "active": False,
    },
    {
        "model_code": "M7_OCSVM_WUSTL", "display_name": "M7 One-Class SVM (Stage 3 baseline)",
        "stage": None, "algorithm": "OneClassSVM", "task_type": "anomaly",
        "artifact_path": "models/one_class_svm_v1.pkl", "results": "novelty_results.json",
        "results_key": "one_class_svm_M7", "active": False,
    },
    {
        "model_code": "M8_LOGREG_WUSTL", "display_name": "M8 Logistic Regression (baseline)",
        "stage": None, "algorithm": "LogisticRegression", "task_type": "binary",
        "artifact_path": None, "results": "binary_results.json",
        "results_key": "logistic_regression", "active": False,
    },
    {
        "model_code": "M9_SVM_RBF_WUSTL", "display_name": "M9 SVM-RBF (baseline)",
        "stage": None, "algorithm": "SVC-RBF", "task_type": "binary",
        "artifact_path": None, "results": "binary_results.json",
        "results_key": "svm_rbf", "active": False,
    },
    {
        "model_code": "M10_STACKING_WUSTL", "display_name": "M10 Stacking Ensemble",
        "stage": None, "algorithm": "LogisticRegression-meta", "task_type": "meta",
        "artifact_path": "models/stacking_meta_v1.pkl", "results": "stacking_results.json",
        "results_key": "stacking_M10", "active": False,
    },
]


def _load(name: str) -> dict | None:
    path = MODELS_DIR / name
    if not path.exists():
        print(f"  ! {name} not found — run the matching ml/ script first")
        return None
    with open(path) as f:
        return json.load(f)


def _metrics_for(payload: dict, key: str) -> dict | None:
    """Digs the test metrics out of whichever shape the script wrote."""
    if payload is None:
        return None
    if key in payload:                      # binary_results / novelty_results
        entry = payload[key]
        return entry.get("test", entry)
    test = payload.get("test", {})          # stacking_results
    return test.get(key)


def _upsert_model(db: Session, spec: dict) -> MlModel:
    model = db.query(MlModel).filter(MlModel.model_code == spec["model_code"]).first()
    if model is None:
        model = MlModel(model_code=spec["model_code"], version="v1")
        db.add(model)
    model.display_name = spec["display_name"]
    model.stage = spec["stage"]
    model.algorithm = spec["algorithm"]
    model.task_type = spec["task_type"]
    model.feature_set_version = "v1"
    # Baselines have no deployable artifact; the column is NOT NULL, so record
    # where they were measured instead of inventing a path.
    model.artifact_path = spec["artifact_path"] or f"(not deployed — see models/{spec['results']})"
    model.scaler_path = "data/scalers/scaler_v1.pkl"
    if model.trained_at is None:
        model.trained_at = datetime.utcnow()
    db.flush()
    return model


def _upsert_run(db: Session, model: MlModel, dataset: Dataset | None, metrics: dict) -> TrainingRun:
    # One run per model here — these were single fits, not sweeps. A stable
    # run_uid keeps re-running this script from stacking duplicate history.
    run_uid = str(uuid.uuid5(uuid.NAMESPACE_URL, f"iomt/{model.model_code}/v1"))
    run = db.query(TrainingRun).filter(TrainingRun.run_uid == run_uid).first()
    if run is None:
        run = TrainingRun(run_uid=run_uid, model_id=model.id)
        db.add(run)
    run.dataset_id = dataset.id if dataset else None
    run.resampling_method = "SMOTE (training split only)"
    run.status = "completed"
    run.duration_seconds = int(metrics.get("train_seconds") or 0) or None
    run.finished_at = run.finished_at or datetime.utcnow()
    run.notes = "registered by backend/register_models.py from the ml/ results files"
    db.flush()
    return run


def _replace_metrics(db: Session, run: TrainingRun, metrics: dict) -> None:
    db.query(ModelMetric).filter(ModelMetric.training_run_id == run.id).delete()
    cm = metrics.get("confusion_matrix")
    fpr = metrics.get("false_positive_rate")
    if fpr is None and cm:
        (tn, fp), _ = cm
        fpr = fp / (fp + tn) if (fp + tn) else None
    db.add(ModelMetric(
        training_run_id=run.id,
        split="test",
        accuracy=metrics.get("accuracy"),
        precision=metrics.get("precision"),
        recall=metrics.get("recall") or metrics.get("detection_rate"),
        f1_score=metrics.get("f1"),
        roc_auc=metrics.get("roc_auc"),
        false_positive_rate=fpr,
        confusion_matrix=cm,
        avg_inference_ms=metrics.get("inference_ms_per_flow"),
    ))


def _replace_importances(db: Session, model: MlModel, artifact: str) -> int:
    """Feature importances straight from the fitted estimator, top 25."""
    path = PROJECT_ROOT / artifact
    if not path.exists():
        return 0
    estimator = joblib.load(path)
    if not hasattr(estimator, "feature_importances_"):
        return 0
    with open(MODELS_DIR / "feature_order.json") as f:
        features = json.load(f)["features"]
    values = list(estimator.feature_importances_)
    if len(values) != len(features):
        print(f"  ! {model.model_code}: {len(values)} importances for {len(features)} "
              f"features — skipping rather than mislabelling them")
        return 0

    db.query(FeatureImportance).filter(FeatureImportance.model_id == model.id).delete()
    ranked = sorted(zip(features, values), key=lambda kv: -kv[1])[:25]
    for rank, (name, gain) in enumerate(ranked, start=1):
        db.add(FeatureImportance(
            model_id=model.id, feature_name=name.strip(),
            importance_gain=round(float(gain), 8), rank=rank,
        ))
    return len(ranked)


def main() -> None:
    db = SessionLocal()
    try:
        dataset = db.query(Dataset).filter(Dataset.name == "WUSTL-EHMS-2020").first()
        if dataset is None:
            print("! dataset WUSTL-EHMS-2020 is not registered; runs will have no dataset link")

        cache: dict[str, dict | None] = {}
        registered = 0
        for spec in REGISTRY:
            if spec["results"] not in cache:
                cache[spec["results"]] = _load(spec["results"])
            metrics = _metrics_for(cache[spec["results"]], spec["results_key"])
            if metrics is None:
                print(f"  ! no metrics for {spec['model_code']} — skipped")
                continue

            model = _upsert_model(db, spec)
            run = _upsert_run(db, model, dataset, metrics)
            _replace_metrics(db, run, metrics)
            n_imp = _replace_importances(db, model, spec["artifact_path"]) \
                if spec["artifact_path"] else 0

            headline = metrics.get("f1") or metrics.get("detection_rate") or 0
            print(f"  {spec['model_code']:<24} stage={spec['stage'] or '-':<4} "
                  f"score={headline:.4f}  importances={n_imp}")
            registered += 1

        db.commit()
        print(f"\nRegistered {registered} models with their test metrics.")

        active = db.query(MlModel).filter(MlModel.is_active.is_(True)).all()
        print("Active pipeline stages (unchanged by this script):")
        for m in sorted(active, key=lambda m: m.stage or 0):
            print(f"  stage {m.stage}: {m.model_code}")
    finally:
        db.close()


if __name__ == "__main__":
    main()
