from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.system_config import SystemConfig


def list_configs(db: Session) -> list[SystemConfig]:
    return db.query(SystemConfig).order_by(SystemConfig.config_key).all()


def get_config(db: Session, config_key: str) -> SystemConfig | None:
    return db.query(SystemConfig).filter(SystemConfig.config_key == config_key).first()


def create_config(db: Session, *, config_key: str, config_value: str | None, value_type: str,
                   description: str | None, actor_user_id: int) -> SystemConfig:
    config = SystemConfig(
        config_key=config_key,
        config_value=config_value,
        value_type=value_type,
        description=description,
        updated_by=actor_user_id,
    )
    db.add(config)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "config_key already exists")
    db.refresh(config)
    return config


def update_config(db: Session, *, config_key: str, updates: dict, actor_user_id: int) -> SystemConfig:
    config = db.query(SystemConfig).filter(SystemConfig.config_key == config_key).first()
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "config key not found")
    for field, value in updates.items():
        setattr(config, field, value)
    config.updated_by = actor_user_id
    db.commit()
    db.refresh(config)
    return config


def delete_config(db: Session, *, config_key: str) -> None:
    config = db.query(SystemConfig).filter(SystemConfig.config_key == config_key).first()
    if config is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "config key not found")
    db.delete(config)
    db.commit()
