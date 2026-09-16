from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.blocklist import BlocklistEntry
from services import safety_service


def list_entries(db: Session, *, entry_type: str | None = None, is_active: bool | None = None):
    query = db.query(BlocklistEntry)
    if entry_type:
        query = query.filter(BlocklistEntry.entry_type == entry_type)
    if is_active is True:
        # "Active" has to mean actually in force. expires_at was being written
        # and never read, so a lapsed block still listed as active.
        query = safety_service.active_blocklist_filter(query)
    elif is_active is False:
        query = query.filter(BlocklistEntry.is_active.is_(False))
    return query.order_by(BlocklistEntry.created_at.desc()).all()


def get_entry(db: Session, entry_id: int) -> BlocklistEntry | None:
    return db.query(BlocklistEntry).filter(BlocklistEntry.id == entry_id).first()


def create_entry(db: Session, *, entry_type: str, value: str, reason: str | None,
                  alert_id: int | None, expires_at, actor_user_id: int) -> BlocklistEntry:
    entry = BlocklistEntry(
        entry_type=entry_type,
        value=value,
        reason=reason,
        alert_id=alert_id,
        expires_at=expires_at,
        added_by=actor_user_id,
    )
    db.add(entry)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "invalid alert_id reference")
    db.refresh(entry)
    return entry


def update_entry(db: Session, *, entry_id: int, updates: dict) -> BlocklistEntry:
    entry = db.query(BlocklistEntry).filter(BlocklistEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "blocklist entry not found")
    for field, value in updates.items():
        setattr(entry, field, value)
    db.commit()
    db.refresh(entry)
    return entry


def delete_entry(db: Session, *, entry_id: int) -> None:
    entry = db.query(BlocklistEntry).filter(BlocklistEntry.id == entry_id).first()
    if entry is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "blocklist entry not found")
    db.delete(entry)
    db.commit()
