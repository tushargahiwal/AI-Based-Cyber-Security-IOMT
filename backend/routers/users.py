from fastapi import APIRouter, Depends, HTTPException, Query, Request, status
from sqlalchemy.orm import Session

from database import get_db
from dependencies import AuthContext, get_current_user, require_permission
from schemas.auth import UserOut
from schemas.user import UserListResponse, UserUpdateRequest
from services import audit_service, user_service

router = APIRouter(prefix="/api/v1/users", tags=["users"])


def _to_user_out(user) -> UserOut:
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
        role=user.role.name,
        permissions=user.role.permissions,
        is_active=user.is_active,
        failed_login_count=user.failed_login_count,
    )


@router.get("", response_model=UserListResponse)
def list_users(
    page: int = Query(1, ge=1),
    size: int = Query(20, ge=1, le=100),
    include_deleted: bool = Query(False),
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("users.manage")),
):
    items, total = user_service.list_users(db, page=page, size=size, include_deleted=include_deleted)
    return UserListResponse(items=[_to_user_out(u) for u in items], total=total, page=page, size=size)


@router.get("/{user_id}", response_model=UserOut)
def get_user(
    user_id: int,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    is_admin = "*" in ctx.permissions or "users.manage" in ctx.permissions
    if not is_admin and ctx.user.id != user_id:
        raise HTTPException(status.HTTP_403_FORBIDDEN, "cannot view another user's profile")

    user = user_service.get_user(db, user_id)
    if user is None:
        raise HTTPException(status.HTTP_404_NOT_FOUND, "user not found")
    return _to_user_out(user)


@router.patch("/{user_id}", response_model=UserOut)
def update_user(
    user_id: int,
    body: UserUpdateRequest,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(get_current_user),
):
    updates = body.model_dump(exclude_unset=True)
    before = user_service.get_user(db, user_id)
    old_value = None
    if before is not None:
        old_value = {
            field: (before.role.name if field == "role" else getattr(before, field, None))
            for field in updates
        }

    user = user_service.update_user(
        db,
        target_user_id=user_id,
        updates=updates,
        actor_user_id=ctx.user.id,
        actor_permissions=ctx.permissions,
    )
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="UPDATE_USER",
        entity_type="users",
        entity_id=user_id,
        old_value=old_value,
        new_value=updates,
        ip_address=request.client.host if request.client else None,
    )
    return _to_user_out(user)


@router.delete("/{user_id}", status_code=status.HTTP_204_NO_CONTENT)
def delete_user(
    user_id: int,
    request: Request,
    db: Session = Depends(get_db),
    ctx: AuthContext = Depends(require_permission("users.manage")),
):
    user_service.delete_user(db, target_user_id=user_id, actor_user_id=ctx.user.id)
    audit_service.log(
        db,
        user_id=ctx.user.id,
        action="DELETE_USER",
        entity_type="users",
        entity_id=user_id,
        ip_address=request.client.host if request.client else None,
    )
