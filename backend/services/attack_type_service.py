from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.attack_type import AttackType


def list_attack_types(db: Session) -> list[AttackType]:
    return db.query(AttackType).order_by(AttackType.family, AttackType.code).all()


def get_attack_type(db: Session, attack_type_id: int) -> AttackType | None:
    return db.query(AttackType).filter(AttackType.id == attack_type_id).first()


def create_attack_type(db: Session, *, data: dict) -> AttackType:
    attack_type = AttackType(**data)
    db.add(attack_type)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "attack_type code already exists")
    db.refresh(attack_type)
    return attack_type


def update_attack_type(db: Session, *, attack_type_id: int, updates: dict) -> AttackType:
    attack_type = db.query(AttackType).filter(AttackType.id == attack_type_id).first()
    if attack_type is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "attack_type not found")
    for field, value in updates.items():
        setattr(attack_type, field, value)
    db.commit()
    db.refresh(attack_type)
    return attack_type
