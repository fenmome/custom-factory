"""认证接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.database import get_session
from app.core.exceptions import UnauthorizedError
from app.core.response import ok
from app.core.security import create_access_token, verify_password
from app.deps import CurrentContext, get_current_context
from app.models.workspace import User, Workspace, WorkspaceMembership
from app.schemas.auth import LoginRequest, LoginResponse, UserBrief, WorkspaceBrief

router = APIRouter()


@router.post("/login", summary="登录并获取 JWT")
async def login(payload: LoginRequest, db: Session = Depends(get_session)):
    user = db.scalar(select(User).where(User.email == payload.email))
    if user is None or not verify_password(payload.password, user.password_hash):
        raise UnauthorizedError(detail="邮箱或密码错误")
    if user.state != "ACTIVE":
        raise UnauthorizedError(detail="账号已停用")

    membership = db.scalar(
        select(WorkspaceMembership).where(
            WorkspaceMembership.user_id == user.id,
            WorkspaceMembership.status == "ACTIVE",
        )
    )
    workspace_id = membership.workspace_id if membership else ""

    token = create_access_token(user_id=user.id, workspace_id=workspace_id)

    workspace: Workspace | None = db.get(Workspace, workspace_id) if workspace_id else None

    return ok(
        LoginResponse(
            token=token,
            expires_hours=settings.ACCESS_TOKEN_EXPIRE_HOURS,
            user=UserBrief(
                id=user.id,
                email=user.email,
                display_name=user.display_name,
                state=user.state,
                is_superuser=user.is_superuser,
            ),
            workspace=(
                WorkspaceBrief(
                    id=workspace.id,
                    display_name=workspace.display_name,
                    state=workspace.state,
                    role=membership.role if membership else "",
                )
                if workspace
                else None
            ),
        ).model_dump()
    )


@router.post("/logout", summary="登出（前端清除本地凭证）")
async def logout(_: CurrentContext = Depends(get_current_context)):
    return ok({"logged_out": True})


@router.get("/me", summary="当前用户与工作空间")
async def me(ctx: CurrentContext = Depends(get_current_context), db: Session = Depends(get_session)):
    workspace = db.get(Workspace, ctx.workspace_id)
    return ok(
        {
            "user": UserBrief(
                id=ctx.user.id,
                email=ctx.user.email,
                display_name=ctx.user.display_name,
                state=ctx.user.state,
                is_superuser=ctx.user.is_superuser,
            ).model_dump(),
            "workspace": (
                WorkspaceBrief(
                    id=workspace.id,
                    display_name=workspace.display_name,
                    state=workspace.state,
                    role=ctx.role,
                ).model_dump()
                if workspace
                else None
            ),
        }
    )
