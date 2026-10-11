"""工作空间接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.response import ok
from app.deps import CurrentContext, get_current_context
from app.models.workspace import Workspace, WorkspaceMembership
from app.schemas.auth import WorkspaceBrief

router = APIRouter()


@router.get("", summary="我的工作空间列表")
async def list_mine(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    rows = db.execute(
        select(Workspace, WorkspaceMembership.role)
        .join(WorkspaceMembership, WorkspaceMembership.workspace_id == Workspace.id)
        .where(
            WorkspaceMembership.user_id == ctx.user_id,
            WorkspaceMembership.status == "ACTIVE",
        )
    ).all()

    items = [
        WorkspaceBrief(
            id=ws.id,
            display_name=ws.display_name,
            state=ws.state,
            role=role,
        ).model_dump()
        for ws, role in rows
    ]
    return ok({"items": items, "current": ctx.workspace_id})
