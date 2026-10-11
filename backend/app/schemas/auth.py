"""认证相关 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, EmailStr, Field


class LoginRequest(BaseModel):
    email: EmailStr
    password: str = Field(..., min_length=6, max_length=128)


class UserBrief(BaseModel):
    id: str
    email: str
    display_name: str
    state: str
    is_superuser: bool = False


class WorkspaceBrief(BaseModel):
    id: str
    display_name: str
    state: str
    role: str


class LoginResponse(BaseModel):
    token: str
    token_type: str = "Bearer"
    expires_hours: int
    user: UserBrief
    workspace: WorkspaceBrief | None = None
