"""Codex Runner 内部接口（仅本机回环 + Runner Token）。

Base URL：`/internal/runner`
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, UploadFile
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.events import SYSTEM_EXCEPTION, record_event
from app.core.exceptions import BatchNotFoundError, ImageJobNotFoundError, ProductionPausedError, ValidationError
from app.core.response import ok
from app.deps import RunnerContext, get_runner_context
from app.models.product import Batch
from app.services import (
    image_service,
    ocr_text_qa_service,
    ready_service,
    revision_qa_service,
    sku_generation_claim_service,
    unified_image_ingest_service,
)
from app.services.batch_preparation_service import BatchProductionPreparationService
from app.services.frozen_sku_plan_store import FrozenSkuPlanStore
from app.services.production_guard_service import ProductionGuardService
from app.services.unified_image_ingest_service import IngestCommand

router = APIRouter(tags=["Runner"])

_UPLOAD_BYTES_LIMIT = 20 * 1024 * 1024  # 20MB


@router.post("/prepare-batch", summary="Runner 触发批次生产准备")
async def prepare_batch(
    batch_id: str,
    operation_key: str = Header(..., alias="X-Operation-Key"),
    ctx: RunnerContext = Depends(get_runner_context),
    db: Session = Depends(get_session),
):
    batch = db.scalar(
        select(Batch).where(Batch.workspace_id == ctx.workspace_id, Batch.id == batch_id)
    )
    if batch is None:
        raise BatchNotFoundError

    result = BatchProductionPreparationService().prepare_batch(
        session=db, workspace_id=ctx.workspace_id, batch_id=batch_id, operation_key=operation_key
    )
    db.commit()
    return ok(
        {
            "batch_id": result.batch_id,
            "prepared_count": result.prepared_count,
            "skipped_count": result.skipped_count,
            "plan_count": result.plan_count,
            "errors": result.errors,
        }
    )


@router.post("/claim-sku", summary="领取下一个可执行 SKU")
async def claim_sku(
    batch_id: str | None = None,
    request_key: str = Header(..., alias="X-Request-Key"),
    ctx: RunnerContext = Depends(get_runner_context),
    db: Session = Depends(get_session),
):
    try:
        claimed = sku_generation_claim_service.claim(
            session=db,
            workspace_id=ctx.workspace_id,
            executor_kind="CODEX",
            executor_id=ctx.executor_id,
            request_key=request_key,
            batch_id=batch_id,
        )
    except ProductionPausedError as exc:
        # 暂停（含最小影响范围 / 试运行上限）以可读载荷返回，Runner 据此退避
        return ok({"claimed": False, "paused": True, "reason": exc.message})
    db.commit()
    if not claimed:
        return ok({"claimed": False, "paused": False})

    plan = FrozenSkuPlanStore().load(workspace_id=ctx.workspace_id, revision_id=claimed["revision_id"])
    return ok({"claimed": True, "claim": claimed, "plan": plan})


@router.post("/heartbeat", summary="领取心跳")
async def heartbeat(
    claim_id: str,
    ctx: RunnerContext = Depends(get_runner_context),
    db: Session = Depends(get_session),
):
    row = sku_generation_claim_service.heartbeat(
        session=db, workspace_id=ctx.workspace_id, claim_id=claim_id
    )
    db.commit()
    return ok({"claim_id": claim_id, "alive": row is not None})


@router.post("/image/{revision_id}/slot/{slot}", summary="Runner 上传槽位图片")
async def upload_image(
    revision_id: str,
    slot: int,
    file: UploadFile = File(...),
    expected_sha256: str | None = Header(default=None, alias="X-Content-Sha256"),
    model: str | None = Header(default=None, alias="X-Image-Model"),
    provider: str | None = Header(default=None, alias="X-Image-Provider"),
    claims: str | None = Header(default=None, alias="X-Claim-Id"),
    ctx: RunnerContext = Depends(get_runner_context),
    db: Session = Depends(get_session),
):
    job = image_service.get_job_by_slot(
        session=db, workspace_id=ctx.workspace_id, revision_id=revision_id, slot=slot
    )
    if job is None:
        raise ImageJobNotFoundError(detail=f"revision={revision_id} slot={slot}")

    data = await file.read()
    if len(data) > _UPLOAD_BYTES_LIMIT:
        raise ValidationError(detail="上传超过 20MB 上限")

    result = unified_image_ingest_service.ingest_png(
        session=db,
        command=IngestCommand(
            workspace_id=ctx.workspace_id,
            revision_id=revision_id,
            slot=slot,
            executor_kind="CODEX",
            executor_id=ctx.executor_id,
            provider=provider,
            model=model,
            operation_key=f"codex:{claims or ctx.executor_id}:{revision_id}:{slot}",
        ),
        data=data,
        declared_sha256=expected_sha256,
    )

    # 每个槽位上传后自动执行 OCR（结果需人工确认）
    ocr_text_qa_service.OCRTextQAService().evaluate(
        session=db,
        asset=result.asset,
        job=result.job,
        operation_key=f"codex:ocr:{revision_id}:{slot}",
    )
    db.commit()

    return ok(
        {
            "slot": slot,
            "asset_id": result.asset.id,
            "technical": result.technical_qa.result,
            "semantic": result.semantic_qa.result,
        }
    )


@router.post("/summarise/{revision_id}", summary="Runner 触发修订 QA 汇总")
async def summarise(
    revision_id: str,
    ctx: RunnerContext = Depends(get_runner_context),
    db: Session = Depends(get_session),
):
    summary = revision_qa_service.RevisionQAService().summarise(
        session=db, workspace_id=ctx.workspace_id, revision_id=revision_id
    )
    db.commit()

    # 试运行期间：修订汇总为 FAIL 即自动上报失败，任一 FAIL → 回退 PAUSED（FR-09）
    if summary.result == "FAIL":
        TrialRecorder.record(session=db, workspace_id=ctx.workspace_id, passed=False)
        db.commit()

    return ok(
        {
            "revision_id": revision_id,
            "result": summary.result,
            "passed_count": summary.passed_count,
            "failed_count": summary.failed_count,
            "pending_count": summary.pending_count,
        }
    )


@router.post("/mark-ready/{product_id}", summary="Runner 标记 READY")
async def mark_ready(
    product_id: str,
    operation_key: str = Header(..., alias="X-Operation-Key"),
    ctx: RunnerContext = Depends(get_runner_context),
    db: Session = Depends(get_session),
):
    result = ready_service.ReadyService().mark_ready(
        session=db, workspace_id=ctx.workspace_id, product_id=product_id, operation_key=operation_key
    )
    db.commit()

    # READY 成功即视为试运行 PASS（失败路径见 /report-fail 与 /summarise）
    TrialRecorder.record(session=db, workspace_id=ctx.workspace_id, passed=True)
    db.commit()
    return ok(result)


@router.post("/report-fail", summary="Runner 上报执行失败（试运行期间任一 FAIL → 重新暂停）")
async def report_fail(
    reason: str,
    claim_id: str | None = None,
    ctx: RunnerContext = Depends(get_runner_context),
    db: Session = Depends(get_session),
):
    if claim_id:
        sku_generation_claim_service.close(session=db, workspace_id=ctx.workspace_id, claim_id=claim_id)
    TrialRecorder.record(session=db, workspace_id=ctx.workspace_id, passed=False)
    db.commit()
    return ok({"reported": True, "reason": reason})


@router.post("/report-exception", summary="Runner 上报非致命系统异常（RED-05：同类连续 ≥3 次 → RED）")
async def report_exception(
    reason_code: str,
    detail: str | None = None,
    ctx: RunnerContext = Depends(get_runner_context),
    db: Session = Depends(get_session),
):
    record_event(
        db,
        workspace_id=ctx.workspace_id,
        entity_type="PRODUCTION",
        entity_id=ctx.workspace_id,
        event_kind=SYSTEM_EXCEPTION,
        payload={"reason_code": reason_code, "detail": detail, "executor_id": ctx.executor_id},
    )
    db.commit()
    return ok({"reported": True, "reason_code": reason_code})


@router.post("/release-claim", summary="释放领取")
async def release_claim(
    claim_id: str,
    ctx: RunnerContext = Depends(get_runner_context),
    db: Session = Depends(get_session),
):
    row = sku_generation_claim_service.close(
        session=db, workspace_id=ctx.workspace_id, claim_id=claim_id
    )
    db.commit()
    return ok({"claim_id": claim_id, "closed": row is not None})


class TrialRecorder:
    """试运行结果上报辅助。"""

    @staticmethod
    def record(*, session: Session, workspace_id: str, passed: bool) -> None:
        controls = ProductionGuardService.active_pauses(session=session, workspace_id=workspace_id)
        trial = next((c for c in controls if c.state == "TRIAL_RUNNING"), None)
        if trial is None:
            return
        ProductionGuardService().record_trial_result(
            session=session,
            workspace_id=workspace_id,
            control_id=trial.id,
            result="PASS" if passed else "FAIL",
        )


