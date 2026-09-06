from datetime import datetime, timedelta

from fastapi import HTTPException, status
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from config import settings
from models.role import Role
from models.user import User
from models.user_session import UserSession
from services.security import (
    create_access_token,
    generate_refresh_token,
    hash_password,
    hash_refresh_token,
    verify_password,
)

MAX_FAILED_LOGINS = 5


def register_user(
    db: Session,
    *,
    username: str,
    email: str,
    password: str,
    role_name: str,
    full_name: str | None,
    department: str | None,
    mobile: str | None,
    address: str | None,
    city: str | None,
    state: str | None,
    requesting_permissions: list | None,
) -> User:
    is_first_user = db.query(User).count() == 0

    # Self-registration always lands as the requested role only if the caller is an
    # already-authenticated admin, or this is the very first account (bootstrap).
    # Otherwise force the least-privileged role to prevent privilege escalation.
    if role_name != "viewer" and not is_first_user:
        if not requesting_permissions or (
            "*" not in requesting_permissions and "users.manage" not in requesting_permissions
        ):
            raise HTTPException(
                status.HTTP_403_FORBIDDEN,
                "only an admin can register a user with a role other than 'viewer'",
            )

    role = db.query(Role).filter(Role.name == role_name).first()
    if role is None:
        raise HTTPException(status.HTTP_400_BAD_REQUEST, f"unknown role '{role_name}'")

    user = User(
        role_id=role.id,
        username=username,
        email=email,
        password_hash=hash_password(password),
        full_name=full_name,
        department=department,
        mobile=mobile,
        address=address,
        city=city,
        state=state,
    )
    db.add(user)
    try:
        db.commit()
    except IntegrityError:
        db.rollback()
        raise HTTPException(status.HTTP_409_CONFLICT, "username or email already registered")
    db.refresh(user)
    return user


def authenticate_user(db: Session, *, username: str, password: str) -> User:
    user = db.query(User).filter(User.username == username).first()
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    if user.failed_login_count >= MAX_FAILED_LOGINS:
        raise HTTPException(
            status.HTTP_423_LOCKED,
            "account locked after too many failed attempts — contact an admin",
        )

    if not verify_password(password, user.password_hash):
        user.failed_login_count += 1
        db.commit()
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid credentials")

    user.failed_login_count = 0
    user.last_login_at = datetime.utcnow()
    db.commit()
    db.refresh(user)
    return user


def issue_tokens(db: Session, user: User, *, ip_address: str | None, user_agent: str | None):
    raw_refresh = generate_refresh_token()
    now = datetime.utcnow()
    session = UserSession(
        user_id=user.id,
        refresh_token_hash=hash_refresh_token(raw_refresh),
        ip_address=ip_address,
        user_agent=user_agent,
        issued_at=now,
        expires_at=now + timedelta(days=settings.refresh_token_expire_days),
        revoked=False,
    )
    db.add(session)
    db.commit()
    db.refresh(session)

    access_token = create_access_token(
        user_id=user.id,
        username=user.username,
        role=user.role.name,
        permissions=user.role.permissions,
        session_id=session.id,
    )
    return access_token, raw_refresh


def refresh_access_token(db: Session, raw_refresh_token: str):
    token_hash = hash_refresh_token(raw_refresh_token)
    session = db.query(UserSession).filter(UserSession.refresh_token_hash == token_hash).first()

    now = datetime.utcnow()
    if session is None or session.revoked or session.expires_at < now:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired refresh token")

    user = db.query(User).filter(User.id == session.user_id).first()
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "invalid or expired refresh token")

    # Rotate: the presented refresh token is single-use. Revoke it and mint a new pair.
    session.revoked = True
    db.commit()

    return issue_tokens(db, user, ip_address=session.ip_address, user_agent=session.user_agent)


def revoke_session(db: Session, *, session_id: int, user_id: int) -> None:
    session = (
        db.query(UserSession)
        .filter(UserSession.id == session_id, UserSession.user_id == user_id)
        .first()
    )
    if session is not None:
        session.revoked = True
        db.commit()
