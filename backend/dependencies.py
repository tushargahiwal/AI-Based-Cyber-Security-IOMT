from dataclasses import dataclass

from fastapi import Depends, HTTPException, Security, status
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from database import get_db
from models.user import User
from services.security import decode_access_token

_bearer_required = HTTPBearer(auto_error=True)
_bearer_optional = HTTPBearer(auto_error=False)


@dataclass
class AuthContext:
    user: User
    role: str
    permissions: list
    session_id: int


def _build_auth_context(token: str, db: Session) -> AuthContext:
    try:
        payload = decode_access_token(token)
    except ValueError:
        raise HTTPException(
            status.HTTP_401_UNAUTHORIZED,
            "invalid or expired token",
            headers={"WWW-Authenticate": "Bearer"},
        )

    user = db.query(User).filter(User.id == int(payload["sub"])).first()
    if user is None or not user.is_active or user.deleted_at is not None:
        raise HTTPException(status.HTTP_401_UNAUTHORIZED, "user not found or inactive")

    return AuthContext(
        user=user,
        role=payload["role"],
        permissions=payload.get("permissions", []),
        session_id=payload["sid"],
    )


def get_current_user(
    credentials: HTTPAuthorizationCredentials = Security(_bearer_required),
    db: Session = Depends(get_db),
) -> AuthContext:
    return _build_auth_context(credentials.credentials, db)


def get_optional_current_user(
    credentials: HTTPAuthorizationCredentials | None = Security(_bearer_optional),
    db: Session = Depends(get_db),
) -> AuthContext | None:
    if credentials is None:
        return None
    try:
        return _build_auth_context(credentials.credentials, db)
    except HTTPException:
        return None


def require_permission(permission: str):
    def _checker(ctx: AuthContext = Depends(get_current_user)) -> AuthContext:
        if "*" not in ctx.permissions and permission not in ctx.permissions:
            raise HTTPException(status.HTTP_403_FORBIDDEN, f"missing permission: {permission}")
        return ctx

    return _checker
