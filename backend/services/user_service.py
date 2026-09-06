from datetime import datetime

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from models.role import Role
from models.user import User
from models.user_session import UserSession

# Only an admin (users.manage) may change these on anyone, including themselves.
PRIVILEGED_FIELDS = {"role", "is_active", "failed_login_count"}
SELF_EDITABLE_FIELDS = {"full_name", "department", "mobile", "address", "city", "state", "email"}


def list_users(db: Session, *, page: int, size: int, include_deleted: bool = False):
    query = db.query(User).order_by(User.id)
    if not include_deleted:
        query = query.filter(User.deleted_at.is_(None))
    total = query.count()
    items = query.offset((page - 1) * size).limit(size).all()
    return items, total


def get_user(db: Session, user_id: int, *, include_deleted: bool = False) -> User | None:
    query = db.query(User).filter(User.id == user_id)
    if not include_deleted:
        query = query.filter(User.deleted_at.is_(None))
    return query.first()


def update_user(
    db: Session,
    *,
    target_user_id: int,
    updates: dict,
    actor_user_id: int,
    actor_permissions: list,
) -> User:
    is_admin = "*" in actor_permissions or "users.manage" in actor_permissions
    is_self = actor_user_id == target_user_id

    if not is_admin and not is_self:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot update another user's profile")

    if not is_admin and (PRIVILEGED_FIELDS & updates.keys()):
        raise HTTPException(
            status.HTTP_403_FORBIDDEN,
            "only an admin can change role, active status, or unlock an account",
        )

    user = db.query(User).filter(User.id == target_user_id, User.deleted_at.is_(None)).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    if "role" in updates:
        role = db.query(Role).filter(Role.name == updates["role"]).first()
        if role is None:
            raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown role '{updates['role']}'")
        user.role_id = role.id

    for field in ("is_active", "failed_login_count", *SELF_EDITABLE_FIELDS):
        if field in updates:
            setattr(user, field, updates[field])

    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "email already in use")
    db.refresh(user)
    return user


def delete_user(db: Session, *, target_user_id: int, actor_user_id: int) -> None:
    """Soft delete: mark deleted_at, deactivate, and kill all live sessions.

    The row (and its history in audit_logs, alerts, ml_models, etc. via FK)
    is kept intact — a hard delete would either cascade-destroy that history
    or fail outright once the user has any real activity on record.
    """
    if target_user_id == actor_user_id:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, "cannot delete your own account")

    user = db.query(User).filter(User.id == target_user_id, User.deleted_at.is_(None)).first()
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")

    user.deleted_at = datetime.utcnow()
    user.is_active = False
    db.query(UserSession).filter(UserSession.user_id == target_user_id).update({"revoked": True})
    db.commit()
