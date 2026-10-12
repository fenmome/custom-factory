"""生产保护接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.events import GUARD_RESOLVED, record_event, utc_now
from app.core.exceptions import NotFoundError, ValidationError
from app.core.response import ok
from app.deps import CurrentContext, get_current_context, require_operator
from app.models.guard import ProductionPauseControl
from app.schemas.guard import GuardStatusResponse, TrialStartRequest
from app.services import sku_generation_claim_service
from app.services.production_guard_service import LEVEL_RED, ProductionGuardService

router = APIRouter()


@router.get("/status", summary="生产保护状态")
async def status(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    result = ProductionGuardService().status(session=db, workspace_id=ctx.workspace_id)
    return ok(GuardStatusResponse(**result).model_dump())


@router.post("/evaluate", summary="触发一次评估（并按规则暂停）")
async def evaluate(
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    evaluation = ProductionGuardService().evaluate_and_apply(
        session=db, workspace_id=ctx.workspace_id
    )
    db.commit()
    return ok(
        {
            "level": evaluation.level,
            "rule_id": evaluation.rule_id,
            "reason": evaluation.reason,
            "metrics": evaluation.metrics,
        }
    )


@router.get("/pauses", summary="暂停列表")
async def pauses(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    rows = ProductionGuardService.active_pauses(session=db, workspace_id=ctx.workspace_id)
    return ok({"items": [ProductionGuardService._pause_brief(p) for p in rows]})


@router.post("/pauses/{control_id}/trial", summary="开始试运行（≤3 SKU）")
async def start_trial(
    control_id: str,
    payload: TrialStartRequest,
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    control = ProductionGuardService().start_trial(
        session=db, workspace_id=ctx.workspace_id, control_id=control_id
    )
    db.commit()
    return ok(ProductionGuardService._pause_brief(control))


@router.post("/pauses/{control_id}/trial/result", summary="上报试运行结果")
async def trial_result(
    control_id: str,
    result: str = "PASS",
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    control = ProductionGuardService().record_trial_result(
        session=db, workspace_id=ctx.workspace_id, control_id=control_id, result=result
    )
    db.commit()
    return ok(ProductionGuardService._pause_brief(control))


@router.get("/claims", summary="活跃 SKU 领取列表")
async def claims(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    rows = sku_generation_claim_service.active_claims(session=db, workspace_id=ctx.workspace_id)
    items = [
        {
            "claim_id": row.id,
            "revision_id": row.revision_id,
            "product_id": row.product_id,
            "batch_id": row.batch_id,
            "executor_kind": row.executor_kind,
            "executor_id": row.executor_id,
            "last_activity_at": row.last_activity_at.isoformat() if row.last_activity_at else None,
        }
        for row in rows
    ]
    return ok({"items": items, "total": len(items)})


@router.post("/critical-stop", summary="紧急停止（全 SCOPE 系统级）")
async def critical_stop(
    reason: str = "手动紧急停止",
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    control = ProductionGuardService().critical_stop(
        session=db, workspace_id=ctx.workspace_id, reason=reason
    )
    db.commit()
    return ok(ProductionGuardService._pause_brief(control))


@router.delete("/pauses/{control_id}", summary="撤销暂停（需填原因并写入审计；试运行中不可撤销）")
async def dismiss(
    control_id: str,
    reason: str = Query(..., min_length=2, description="撤销原因，将写入审计事件"),
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    control = db.get(ProductionPauseControl, control_id)
    if control is None or control.workspace_id != ctx.workspace_id:
        raise NotFoundError(detail="暂停控制不存在")
    if control.state == "TRIAL_RUNNING":
        raise ValidationError(detail="试运行进行中，不允许直接撤销；请等待试运行结果")
    if control.state == "RESOLVED":
        raise ValidationError(detail="该暂停已解除")

    control.state = "RESOLVED"
    control.resolved_at = utc_now()
    control.updated_at = utc_now()
    record_event(
        db,
        workspace_id=ctx.workspace_id,
        entity_type="PRODUCTION",
        entity_id=control.id,
        event_kind=GUARD_RESOLVED,
        payload={"manual": True, "reason": reason, "operator_id": ctx.user_id, "trigger_rule_id": control.trigger_rule_id},
    )
    db.commit()
    return ok({"id": control.id, "state": control.state})


__all__ = ["LEVEL_RED", "router"]
