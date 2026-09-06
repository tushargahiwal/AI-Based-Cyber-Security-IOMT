"""Writes to audit_logs. Call `log()` from a router right after a privileged
write succeeds — decoupled from business-logic services on purpose, so the
services stay focused and every router controls its own action/entity naming.
"""

from sqlalchemy.orm import Session

from models.audit_log import AuditLog


def log(
    db: Session,
    *,
    user_id: int | None,
    action: str,
    entity_type: str | None = None,
    entity_id: int | None = None,
    old_value=None,
    new_value=None,
    ip_address: str | None = None,
) -> None:
    entry = AuditLog(
        user_id=user_id,
        action=action,
        entity_type=entity_type,
        entity_id=entity_id,
        old_value=old_value,
        new_value=new_value,
        ip_address=ip_address,
    )
    db.add(entry)
    db.commit()


def list_logs(
    db: Session,
    *,
    page: int,
    size: int,
    user_id: int | None = None,
    action: str | None = None,
    entity_type: str | None = None,
):
    query = db.query(AuditLog)
    if user_id is not None:
        query = query.filter(AuditLog.user_id == user_id)
    if action:
        query = query.filter(AuditLog.action == action)
    if entity_type:
        query = query.filter(AuditLog.entity_type == entity_type)
    query = query.order_by(AuditLog.created_at.desc())
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total
