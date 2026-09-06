from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.dataset import Dataset


def list_datasets(db: Session) -> list[Dataset]:
    return db.query(Dataset).order_by(Dataset.name).all()


def get_dataset(db: Session, dataset_id: int) -> Dataset | None:
    return db.query(Dataset).filter(Dataset.id == dataset_id).first()


def create_dataset(db: Session, *, data: dict) -> Dataset:
    dataset = Dataset(**data)
    db.add(dataset)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "dataset name already exists")
    db.refresh(dataset)
    return dataset


def update_dataset(db: Session, *, dataset_id: int, updates: dict) -> Dataset:
    dataset = db.query(Dataset).filter(Dataset.id == dataset_id).first()
    if dataset is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "dataset not found")
    for field, value in updates.items():
        setattr(dataset, field, value)
    db.commit()
    db.refresh(dataset)
    return dataset
