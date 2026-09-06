from typing import Optional

from pydantic import BaseModel, EmailStr, Field

from schemas.auth import UserOut


class UserListResponse(BaseModel):
    items: list[UserOut]
    total: int
    page: int
    size: int


class UserUpdateRequest(BaseModel):
    # self-editable (by the account owner, or an admin)
    full_name: Optional[str] = Field(default=None, max_length=150)
    department: Optional[str] = Field(default=None, max_length=100)
    mobile: Optional[str] = Field(default=None, max_length=15, pattern=r"^\+?[0-9\-\s]{7,15}$")
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)
    email: Optional[EmailStr] = None

    # admin-only (requires the 'users.manage' permission)
    role: Optional[str] = None
    is_active: Optional[bool] = None
    failed_login_count: Optional[int] = Field(default=None, ge=0)
