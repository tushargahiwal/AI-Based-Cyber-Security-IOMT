from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.protocol import Protocol


def list_protocols(db: Session) -> list[Protocol]:
    return db.query(Protocol).order_by(Protocol.name).all()


def get_protocol(db: Session, protocol_id: int) -> Protocol | None:
    return db.query(Protocol).filter(Protocol.id == protocol_id).first()


def create_protocol(db: Session, *, name: str, default_port: int | None, is_medical: bool) -> Protocol:
    protocol = Protocol(name=name, default_port=default_port, is_medical=is_medical)
    db.add(protocol)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "protocol name already exists")
    db.refresh(protocol)
    return protocol


def update_protocol(db: Session, *, protocol_id: int, updates: dict) -> Protocol:
    protocol = db.query(Protocol).filter(Protocol.id == protocol_id).first()
    if protocol is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "protocol not found")
    for field, value in updates.items():
        setattr(protocol, field, value)
    db.commit()
    db.refresh(protocol)
    return protocol
