"""生产总览仪表盘接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.core.response import ok
from app.deps import CurrentContext, get_current_context
from app.models.guard import SkuGenerationClaim
from app.models.image import ImageJob, ImageQA, RevisionQA
from app.models.product import Batch, Product, ProductRevision
from app.services.production_guard_service import ProductionGuardService
from app.services.sku_generation_claim_service import count_active

router = APIRouter()


@router.get("/overview", summary="生产总览")
async def overview(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    ws = ctx.workspace_id

    batch_total = int(db.scalar(select(func.count()).select_from(Batch).where(Batch.workspace_id == ws)) or 0)
    product_total = int(db.scalar(select(func.count()).select_from(Product).where(Product.workspace_id == ws)) or 0)

    revision_counts = {
        row[0]: row[1]
        for row in db.execute(
            select(ProductRevision.status, func.count())
            .where(ProductRevision.workspace_id == ws)
            .group_by(ProductRevision.status)
        ).all()
    }

    image_job_counts = {
        row[0]: row[1]
        for row in db.execute(
            select(ImageJob.state, func.count())
            .where(ImageJob.workspace_id == ws)
            .group_by(ImageJob.state)
        ).all()
    }

    qa_counts = {
        row[0]: row[1]
        for row in db.execute(
            select(ImageQA.result, func.count()).where(ImageQA.workspace_id == ws).group_by(ImageQA.result)
        ).all()
    }

    revision_qa = {
        row[0]: row[1]
        for row in db.execute(
            select(RevisionQA.result, func.count())
            .where(RevisionQA.workspace_id == ws)
            .group_by(RevisionQA.result)
        ).all()
    }

    guard_status = ProductionGuardService().status(session=db, workspace_id=ws)

    return ok(
        {
            "counts": {
                "batches": batch_total,
                "products": product_total,
                "revisions": revision_counts,
                "image_jobs": image_job_counts,
                "image_qa": qa_counts,
                "revision_qa": revision_qa,
            },
            "guard": {
                "level": guard_status["level"],
                "pauses": guard_status["pauses"],
                "evaluation": guard_status["evaluation"],
            },
            "active_claims": count_active(session=db, workspace_id=ws),
        }
    )


@router.get("/batches/{batch_id}/progress", summary="批次进度明细")
async def batch_progress(
    batch_id: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    batch = db.scalar(select(Batch).where(Batch.workspace_id == ctx.workspace_id, Batch.id == batch_id))
    if batch is None:
        raise NotFoundError(detail="批次不存在")

    revisions = db.scalars(
        select(ProductRevision)
        .where(ProductRevision.workspace_id == ctx.workspace_id, ProductRevision.batch_id == batch_id)
        .order_by(ProductRevision.created_at)
    ).all()

    by_status: dict[str, int] = {}
    for revision in revisions:
        by_status[revision.status] = by_status.get(revision.status, 0) + 1

    image_total = 0
    image_done = 0
    for revision in revisions:
        jobs = db.scalars(select(ImageJob).where(ImageJob.revision_id == revision.id)).all()
        image_total += len(jobs)
        image_done += sum(1 for j in jobs if j.state in {"ASSET_RECORDED", "SETTLED"})

    return ok(
        {
            "batch_id": batch_id,
            "requested_quantity": batch.requested_quantity,
            "allocated_count": len(revisions),
            "by_status": by_status,
            "image_total": image_total,
            "image_done": image_done,
            "image_percent": round(image_done / image_total * 100, 1) if image_total else 0.0,
            "prepared_at": batch.prepared_at.isoformat() if batch.prepared_at else None,
        }
    )


@router.get("/claims", summary="领取协调面板")
async def claims_panel(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    rows = db.scalars(
        select(SkuGenerationClaim)
        .where(SkuGenerationClaim.workspace_id == ctx.workspace_id, SkuGenerationClaim.state == "ACTIVE")
        .order_by(SkuGenerationClaim.last_activity_at.desc())
    ).all()
    return ok(
        {
            "items": [
                {
                    "claim_id": row.id,
                    "internal_sku": _sku(db, row.product_id),
                    "executor_kind": row.executor_kind,
                    "executor_id": row.executor_id,
                    "last_activity_at": row.last_activity_at.isoformat() if row.last_activity_at else None,
                }
                for row in rows
            ]
        }
    )


def _sku(db: Session, product_id: str) -> str:
    product = db.get(Product, product_id)
    return product.internal_sku if product else ""
