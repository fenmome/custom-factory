"""批次接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.events import utc_now
from app.core.exceptions import BatchNotFoundError
from app.core.idempotency import begin, complete
from app.core.response import ok, paged
from app.deps import CurrentContext, get_current_context, require_operator
from app.schemas.batch import BatchCreateRequest, BatchDetailResponse, BatchItem, BatchSummary, PrepareResponse
from app.services import batch_service, product_data_service, revision_qa_service
from app.services.batch_preparation_service import BatchProductionPreparationService
from app.services.batch_service import CreateBatchCommand

router = APIRouter()


@router.post("", summary="创建批次并原子分配 SKU")
async def create_batch(
    payload: BatchCreateRequest,
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    command = CreateBatchCommand(
        workspace_id=ctx.workspace_id,
        product_type_code=payload.product_type_code,
        usage_code=payload.usage_code,
        quantity=payload.quantity,
        image_generation_route=payload.image_generation_route,
        style_code=payload.style_code,
        palette_code=payload.palette_code,
        request_key=payload.request_key,
        operation_key=payload.operation_key,
        created_by_user_id=ctx.user_id,
    )

    begin(
        db,
        workspace_id=ctx.workspace_id,
        operation_key=payload.operation_key,
        scope="batch.create",
        payload=command.snapshot(),
    )
    try:
        batch = batch_service.create_batch(session=db, command=command)
        db.commit()
    except Exception:
        db.rollback()
        raise

    complete(
        db,
        workspace_id=ctx.workspace_id,
        operation_key=payload.operation_key,
        scope="batch.create",
        response_snapshot={"batch_id": batch.id},
    )
    db.commit()

    # 触发批次生产准备
    result = BatchProductionPreparationService().prepare_batch(
        session=db, workspace_id=ctx.workspace_id, batch_id=batch.id, operation_key=payload.operation_key
    )
    db.commit()

    return ok(
        {
            "batch": BatchSummary.model_validate(batch, from_attributes=True).model_dump(),
            "preparation": {
                "prepared_count": result.prepared_count,
                "skipped_count": result.skipped_count,
                "plan_count": result.plan_count,
                "errors": result.errors,
            },
        }
    )


@router.get("", summary="批次列表")
async def list_batches(
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    items = batch_service.list_batches(
        session=db, workspace_id=ctx.workspace_id, limit=page_size, offset=(page - 1) * page_size
    )
    total = batch_service.count_batches(session=db, workspace_id=ctx.workspace_id)
    payload = [BatchSummary.model_validate(item, from_attributes=True).model_dump() for item in items]
    return paged(payload, total=total, page=page, page_size=page_size)


@router.get("/{batch_id}", summary="批次详情（SKU 进度）")
async def get_batch(
    batch_id: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    batch = batch_service.get_batch(session=db, workspace_id=ctx.workspace_id, batch_id=batch_id)
    if batch is None:
        raise BatchNotFoundError

    revisions = batch_service.list_revisions(session=db, workspace_id=ctx.workspace_id, batch_id=batch_id)

    items: list[dict] = []
    counts = {"total": len(revisions), "ready": 0, "frozen": 0, "draft": 0}
    for revision in revisions:
        jobs = _jobs_of(db, revision.id)
        total_jobs = len(jobs)
        settled = sum(1 for j in jobs if j.state == "SETTLED")
        recorded = sum(1 for j in jobs if j.state == "ASSET_RECORDED")
        if revision.status == "READY_FOR_PUBLISH":
            counts["ready"] += 1
        elif revision.status == "FROZEN":
            counts["frozen"] += 1
        else:
            counts["draft"] += 1

        items.append(
            BatchItem(
                id=revision.batch_id,
                product_id=revision.product_id,
                internal_sku=_sku_of(db, revision.product_id),
                revision_id=revision.id,
                revision_status=revision.status,
                image_progress={"total": total_jobs, "settled": settled, "asset_recorded": recorded},
            ).model_dump()
        )

    return ok(
        BatchDetailResponse(
            batch=BatchSummary.model_validate(batch, from_attributes=True),
            items=[BatchItem.model_validate(i) for i in items],
            counts=counts,
        ).model_dump()
    )


@router.post("/{batch_id}/prepare", summary="重试批次生产准备")
async def prepare_batch(
    batch_id: str,
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    result = BatchProductionPreparationService().prepare_batch(
        session=db,
        workspace_id=ctx.workspace_id,
        batch_id=batch_id,
        operation_key=f"webhook:{batch_id}:{utc_now().timestamp()}",
    )
    db.commit()
    return ok(
        PrepareResponse(
            batch_id=result.batch_id,
            prepared_count=result.prepared_count,
            skipped_count=result.skipped_count,
            plan_count=result.plan_count,
            errors=result.errors,
        ).model_dump()
    )


def _jobs_of(db: Session, revision_id: str):
    from sqlalchemy import select

    from app.models.image import ImageJob

    return list(db.scalars(select(ImageJob).where(ImageJob.revision_id == revision_id)).all())


def _sku_of(db: Session, product_id: str) -> str:
    from app.models.product import Product

    product = db.get(Product, product_id)
    return product.internal_sku if product else ""


def _ensure_product_data(db: Session, ctx: CurrentContext, revision) -> None:
    summary = revision_qa_service.latest_summary(
        session=db, workspace_id=ctx.workspace_id, revision_id=revision.id
    )
    product_data_service.build_or_refresh(
        session=db,
        workspace_id=ctx.workspace_id,
        revision=revision,
        qa_snapshot={
            "passed": summary.passed_count if summary else 0,
            "failed": summary.failed_count if summary else 0,
            "pending": summary.pending_count if summary else 0,
            "required_role_status": summary.required_role_status if summary else {},
        },
    )
