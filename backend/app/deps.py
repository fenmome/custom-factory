"""依赖注入：会话、当前用户、当前工作空间。"""

from __future__ import annotations

from collections.abc import Iterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import SessionLocal
from app.core.exceptions import ForbiddenError, UnauthorizedError
from app.core.security import constant_time_equals, decode_access_token
from app.config import settings
from app.models.workspace import User, Workspace, WorkspaceMembership

bearer_scheme = HTTPBearer(auto_error=False)


def get_db() -> Iterator[Session]:
    session = SessionLocal()
    try:
        yield session
    finally:
        session.close()


class CurrentContext:
    """已认证上下文（用户 + 工作空间 + 角色）。"""

    def __init__(self, *, user: User, workspace_id: str, role: str) -> None:
        self.user = user
        self.workspace_id = workspace_id
        self.role = role

    @property
    def user_id(self) -> str:
        return self.user.id


def _unauthorized(detail: str = "缺少或无效的认证凭证") -> UnauthorizedError:
    return UnauthorizedError(detail=detail)


def get_current_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> CurrentContext:
    """解析 Bearer token 并校验 workspace 成员关系。"""
    token = credentials.credentials if credentials is not None else None
    if not token:
        # 兼容查询串传 token（图片 <img src> 场景）
        token = request.query_params.get("token")

    if not token:
        raise _unauthorized()

    payload = decode_access_token(token)
    if not payload:
        raise _unauthorized("凭证无效或已过期")

    user_id = payload.get("sub")
    workspace_id = payload.get("ws")
    if not user_id or not workspace_id:
        raise _unauthorized("凭证缺少身份信息")

    user = db.get(User, user_id)
    if user is None or user.state != "ACTIVE":
        raise _unauthorized("用户不存在或已停用")

    workspace = db.get(Workspace, workspace_id)
    if workspace is None or workspace.state != "ACTIVE":
        raise ForbiddenError(detail="工作空间不可用")

    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user_id,
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.status == "ACTIVE",
        )
    )
    if membership is None:
        raise ForbiddenError(detail="非该工作空间成员")

    return CurrentContext(user=user, workspace_id=workspace_id, role=membership.role)


def require_role(*allowed: str):
    """角色守卫。"""

    def _guard(ctx: CurrentContext = Depends(get_current_context)) -> CurrentContext:
        if allowed and ctx.role not in allowed and not ctx.user.is_superuser:
            raise ForbiddenError(detail=f"需要以下角色之一: {', '.join(allowed)}")
        return ctx

    return _guard


# OWNER 可管理配置；OWNER/MEMBER 可操作生产；REVIEWER 仅复审
require_admin = require_role("OWNER")
require_operator = require_role("OWNER", "MEMBER")
require_reviewer = require_role("OWNER", "MEMBER", "REVIEWER")


class RunnerContext:
    """Runner（Codex）身份上下文。"""

    def __init__(self, *, executor_id: str, workspace_id: str) -> None:
        self.executor_id = executor_id
        self.workspace_id = workspace_id


def get_runner_context(
    request: Request,
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer_scheme),
    db: Session = Depends(get_db),
) -> RunnerContext:
    """校验 Runner 静态 Token（仅本机回环）+ 成员关系。"""
    host = request.client.host if request.client else None
    if host not in {"127.0.0.1", "::1", "localhost"}:
        raise ForbiddenError(detail="Runner API 仅允许本机访问")

    token = credentials.credentials if credentials is not None else request.headers.get("X-Runner-Token")
    if not token or not constant_time_equals(token, settings.RUNNER_TOKEN):
        raise UnauthorizedError(detail="Runner Token 无效")

    executor_id = request.headers.get("X-Runner-Id") or "local-codex"
    workspace_id = request.headers.get("X-Workspace-Id") or ""
    if not workspace_id:
        raise UnauthorizedError(detail="缺少 X-Workspace-Id")

    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.workspace_id == workspace_id,
            WorkspaceMembership.status == "ACTIVE",
        )
    )
    if membership is None:
        raise ForbiddenError(detail="工作空间不存在或无成员")

    return RunnerContext(executor_id=executor_id, workspace_id=workspace_id)
