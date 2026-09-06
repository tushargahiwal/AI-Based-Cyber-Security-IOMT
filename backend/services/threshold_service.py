from fastapi import HTTPException, status
from sqlalchemy.orm import Session

from models.threshold import Threshold


def list_thresholds(db: Session, *, scope: str | None = None, metric: str | None = None) -> list[Threshold]:
    query = db.query(Threshold)
    if scope:
        query = query.filter(Threshold.scope == scope)
    if metric:
        query = query.filter(Threshold.metric == metric)
    return query.order_by(Threshold.scope, Threshold.metric).all()


def get_threshold(db: Session, threshold_id: int) -> Threshold | None:
    return db.query(Threshold).filter(Threshold.id == threshold_id).first()


def create_threshold(db: Session, *, data: dict) -> Threshold:
    threshold = Threshold(**data)
    db.add(threshold)
    db.commit()
    db.refresh(threshold)
    return threshold


def update_threshold(db: Session, *, threshold_id: int, updates: dict) -> Threshold:
    threshold = db.query(Threshold).filter(Threshold.id == threshold_id).first()
    if threshold is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "threshold not found")
    for field, value in updates.items():
        setattr(threshold, field, value)
    db.commit()
    db.refresh(threshold)
    return threshold


def delete_threshold(db: Session, *, threshold_id: int) -> None:
    threshold = db.query(Threshold).filter(Threshold.id == threshold_id).first()
    if threshold is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "threshold not found")
    db.delete(threshold)
    db.commit()
