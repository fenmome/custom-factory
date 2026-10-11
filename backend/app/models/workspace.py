"""Workspace / User / Membership —— 多工作空间隔离模型。"""

from __future__ import annotations

from sqlalchemy import Boolean, DateTime, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time_utils import utc_now
from app.models.base import UUIDType, Base, TimestampMixin


class Workspace(Base, TimestampMixin):
    __tablename__ = "workspaces"

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", server_default="ACTIVE")


class User(Base, TimestampMixin):
    __tablename__ = "users"

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    password_hash: Mapped[str] = mapped_column(String(255), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", server_default="ACTIVE")
    is_superuser: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")


class WorkspaceMembership(Base):
    __tablename__ = "workspace_memberships"
    __table_args__ = (UniqueConstraint("workspace_id", "user_id", name="uk_ws_user"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    user_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    role: Mapped[str] = mapped_column(String(16), nullable=False, default="MEMBER", server_default="MEMBER")
    status: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", server_default="ACTIVE")
    joined_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
    revoked_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
