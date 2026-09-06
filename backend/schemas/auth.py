from typing import Optional

from pydantic import BaseModel, EmailStr, Field


class RegisterRequest(BaseModel):
    username: str = Field(min_length=3, max_length=64)
    email: EmailStr
    password: str = Field(min_length=8, max_length=72)
    role: str = Field(default="viewer")
    full_name: Optional[str] = Field(default=None, max_length=150)
    department: Optional[str] = Field(default=None, max_length=100)
    mobile: Optional[str] = Field(default=None, max_length=15, pattern=r"^\+?[0-9\-\s]{7,15}$")
    address: Optional[str] = Field(default=None, max_length=255)
    city: Optional[str] = Field(default=None, max_length=100)
    state: Optional[str] = Field(default=None, max_length=100)


class LoginRequest(BaseModel):
    username: str
    password: str


class RefreshRequest(BaseModel):
    refresh_token: str


class TokenResponse(BaseModel):
    access_token: str
    refresh_token: str
    token_type: str = "bearer"
    expires_in: int


class UserOut(BaseModel):
    id: int
    username: str
    email: str
    full_name: Optional[str] = None
    department: Optional[str] = None
    mobile: Optional[str] = None
    address: Optional[str] = None
    city: Optional[str] = None
    state: Optional[str] = None
    role: str
    permissions: list
    is_active: bool
    failed_login_count: int = 0

    model_config = {"from_attributes": True}
