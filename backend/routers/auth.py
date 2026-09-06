from fastapi import APIRouter, Depends, Request, status
from sqlalchemy.orm import Session

from config import settings
from database import get_db
from dependencies import AuthContext, get_current_user, get_optional_current_user
from schemas.auth import LoginRequest, RefreshRequest, RegisterRequest, TokenResponse, UserOut
from services import audit_service, auth_service

router = APIRouter(prefix="/api/v1/auth", tags=["auth"])


def _to_user_out(user, role: str, permissions: list) -> UserOut:
    return UserOut(
        id=user.id,
        username=user.username,
        email=user.email,
        full_name=user.full_name,
        department=user.department,
        mobile=user.mobile,
        address=user.address,
        city=user.city,
        state=user.state,
        role=role,
        permissions=permissions,
        is_active=user.is_active,
        failed_login_count=user.failed_login_count,
    )


@router.post("/register", response_model=UserOut, status_code=status.HTTP_201_CREATED)
def register(
    body: RegisterRequest,
    request: Request,
    db: Session = Depends(get_db),
    current_user: AuthContext | None = Depends(get_optional_current_user),
):
    user = auth_service.register_user(
        db,
        username=body.username,
        email=body.email,
        password=body.password,
        role_name=body.role,
        full_name=body.full_name,
        department=body.department,
        mobile=body.mobile,
        address=body.address,
        city=body.city,
        state=body.state,
        requesting_permissions=current_user.permissions if current_user else None,
    )
    audit_service.log(
        db,
        user_id=current_user.user.id if current_user else user.id,
        action="REGISTER",
        entity_type="users",
        entity_id=user.id,
        new_value={"username": user.username, "role": user.role.name},
        ip_address=request.client.host if request.client else None,
    )
    return _to_user_out(user, user.role.name, user.role.permissions)


@router.post("/login", response_model=TokenResponse)
def login(body: LoginRequest, request: Request, db: Session = Depends(get_db)):
    user = auth_service.authenticate_user(db, username=body.username, password=body.password)
    access_token, refresh_token = auth_service.issue_tokens(
        db,
        user,
        ip_address=request.client.host if request.client else None,
        user_agent=request.headers.get("user-agent"),
    )
    audit_service.log(
        db,
        user_id=user.id,
        action="LOGIN",
        entity_type="users",
        entity_id=user.id,
        ip_address=request.client.host if request.client else None,
    )
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/refresh", response_model=TokenResponse)
def refresh(body: RefreshRequest, db: Session = Depends(get_db)):
    access_token, refresh_token = auth_service.refresh_access_token(db, body.refresh_token)
    return TokenResponse(
        access_token=access_token,
        refresh_token=refresh_token,
        expires_in=settings.access_token_expire_minutes * 60,
    )


@router.post("/logout", status_code=status.HTTP_204_NO_CONTENT)
def logout(
    request: Request,
    ctx: AuthContext = Depends(get_current_user),
    db: Session = Depends(get_db),
):
    auth_service.revoke_session(db, session_id=ctx.session_id, user_id=ctx.user.id)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="LOGOUT",
        entity_type="users",
        entity_id=ctx.user.id,
        ip_address=request.client.host if request.client else None,
    )


@router.get("/me", response_model=UserOut)
def me(ctx: AuthContext = Depends(get_current_user)):
    return _to_user_out(ctx.user, ctx.role, ctx.permissions)
