"""人工复审接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.idempotency import begin, complete
from app.core.response import ok, paged
from app.deps import CurrentContext, get_current_context, require_reviewer
from app.models.image import ImageQA, RevisionQA
from app.models.product import Batch, Product, ProductRevision
from app.schemas.review import ReviewDecisionIn, ReviewSubmitRequest, ReviewView, SnapshotItemIn
from app.services.qa_review_service import QAReviewService, ReviewDecision, ReviewSnapshotItem

router = APIRouter()


@router.get("/pending", summary="待复审队列")
async def pending_queue(
    batch_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    stmt = (
        select(Product, ProductRevision, Batch.id.label("batch_id"), Batch.request_key)
        .join(ProductRevision, ProductRevision.product_id == Product.id)
        .join(Batch, ProductRevision.batch_id == Batch.id)
        .where(
            Product.workspace_id == ctx.workspace_id,
            ProductRevision.status != "READY_FOR_PUBLISH",
        )
    )
    if batch_id:
        stmt = stmt.where(ProductRevision.batch_id == batch_id)

    rows = db.execute(stmt).all()
    total = len(rows)
    window = rows[(page - 1) * page_size : page * page_size]

    items = [
        {
            "product_id": product.id,
            "internal_sku": product.internal_sku,
            "revision_id": revision.id,
            "revision_status": revision.status,
            "batch_id": batch_id_value,
            "request_key": request_key,
        }
        for product, revision, batch_id_value, request_key in window
    ]
    return paged(items, total=total, page=page, page_size=page_size)


@router.get("/{product_id}", summary="SKU 复审视图（按集合，8 张）")
async def get_review_view(
    product_id: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    view = QAReviewService().build_review_view(
        session=db, workspace_id=ctx.workspace_id, product_id=product_id
    )
    return ok(
        ReviewView(
            product_id=view["product_id"],
            internal_sku=view["internal_sku"],
            revision_id=view["revision_id"],
            revision_status=view["revision_status"],
            brand_name=view["brand_name"],
            object=view["object"],
            title_text=view["title_text"],
            items=view["items"],
            snapshot=view["snapshot"],
        ).model_dump()
    )


@router.post("/{product_id}/submit", summary="提交复审结论（追加式）")
async def submit_review(
    product_id: str,
    payload: ReviewSubmitRequest,
    ctx: CurrentContext = Depends(require_reviewer),
    db: Session = Depends(get_session),
):
    begin(
        db,
        workspace_id=ctx.workspace_id,
        operation_key=payload.operation_key,
        scope="review.submit",
        payload={
            "product_id": product_id,
            "decisions": [d.model_dump() for d in payload.decisions],
        },
    )

    decisions = [
        ReviewDecision(
            slot=d.slot,
            decision=d.decision,
            reason_code=d.reason_code,
            note=d.note,
        )
        for d in payload.decisions
    ]
    snapshot = [ReviewSnapshotItem(asset_id=s.asset_id, checksum=s.checksum) for s in payload.snapshot]

    try:
        result = QAReviewService().submit(
            session=db,
            command=_build_command(payload, ctx, product_id, decisions, snapshot),
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    complete(
        db,
        workspace_id=ctx.workspace_id,
        operation_key=payload.operation_key,
        scope="review.submit",
        response_snapshot=result,
    )
    db.commit()
    return ok(result)


def _build_command(payload: ReviewSubmitRequest, ctx: CurrentContext, product_id: str, decisions, snapshot):
    from app.services.qa_review_service import SubmitReviewCommand

    return SubmitReviewCommand(
        workspace_id=ctx.workspace_id,
        product_id=product_id,
        operation_key=payload.operation_key,
        reviewer_id=ctx.user_id,
        decisions=decisions,
        snapshot=snapshot,
        complete_set=payload.complete_set,
    )


@router.get("/stats/summary", summary="复审统计（人工 vs 自动）")
async def review_stats(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    rows = db.scalars(
        select(ImageQA).where(ImageQA.workspace_id == ctx.workspace_id, ImageQA.kind == "HUMAN")
    ).all()

    human_pass = sum(1 for r in rows if r.result == "PASS")
    human_fail = sum(1 for r in rows if r.result == "FAIL")

    revision_rows = db.scalars(
        select(RevisionQA.result).where(RevisionQA.workspace_id == ctx.workspace_id)
    ).all()
    auto_pass = sum(1 for r in revision_rows if r == "PASS")

    total_products = int(
        db.scalar(
            select(func.count())
            .select_from(Product)
            .where(Product.workspace_id == ctx.workspace_id)
        )
        or 0
    )

    return ok(
        {
            "total_products": total_products,
            "human_pass": human_pass,
            "human_fail": human_fail,
            "auto_revision_pass": auto_pass,
        }
    )
