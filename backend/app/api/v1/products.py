"""商品 / SKU 接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.exceptions import NotFoundError
from app.core.idempotency import begin, complete
from app.core.response import ok, paged
from app.deps import CurrentContext, get_current_context, require_operator
from app.models.image import ImageAsset, ImageAttempt, ImageJob
from app.models.product import ListingConcept, Product, ProductRevision
from app.schemas.product import ImageBrief, ReadyGateView, ReadyRequest, ReadyResponse, SkuDetail
from app.services import image_qa_service, product_data_service, ready_service, revision_qa_service

router = APIRouter()


@router.get("", summary="SKU 列表")
async def list_products(
    batch_id: str | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=200),
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    stmt = select(Product).where(Product.workspace_id == ctx.workspace_id)
    if batch_id:
        stmt = stmt.where(Product.batch_id == batch_id)
    total = len(db.scalars(stmt).all())
    items = db.scalars(stmt.order_by(Product.internal_sku).limit(page_size).offset((page - 1) * page_size)).all()

    payload = []
    for product in items:
        revision = _active_revision(db, ctx.workspace_id, product.id)
        payload.append(
            {
                "product_id": product.id,
                "internal_sku": product.internal_sku,
                "batch_id": product.batch_id,
                "revision_status": revision.status if revision else None,
                "state": product.state,
            }
        )
    return paged(payload, total=total, page=page, page_size=page_size)


@router.get("/{product_id}", summary="SKU 详情")
async def get_product(
    product_id: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    product = db.scalar(
        select(Product).where(Product.workspace_id == ctx.workspace_id, Product.id == product_id)
    )
    if product is None:
        raise NotFoundError(detail="商品不存在")

    revision = _active_revision(db, ctx.workspace_id, product.id)
    if revision is None:
        raise NotFoundError(detail="无可用修订")

    concept = db.get(ListingConcept, revision.concept_id)
    jobs = db.scalars(
        select(ImageJob).where(ImageJob.revision_id == revision.id).order_by(ImageJob.slot)
    ).all()

    images: list[ImageBrief] = []
    for job in jobs:
        asset = _latest_asset(db, job.id)
        if asset is None:
            images.append(
                ImageBrief(
                    slot=job.slot, role=job.role, is_required=job.is_required, job_state=job.state
                )
            )
            continue
        images.append(
            ImageBrief(
                slot=job.slot,
                role=job.role,
                is_required=job.is_required,
                job_state=job.state,
                asset_id=asset.id,
                width=asset.width,
                height=asset.height,
                integrity_state=asset.integrity_state,
                effective_result=image_qa_service.ImageQAService.effective_result(db, asset_id=asset.id),
                technical=_brief(db, asset.id, image_qa_service.KIND_TECHNICAL),
                semantic=_brief(db, asset.id, image_qa_service.KIND_SEMANTIC),
                human=_brief(db, asset.id, image_qa_service.KIND_HUMAN),
                ocr=_brief(db, asset.id, image_qa_service.KIND_OCR),
            )
        )

    gate = ready_service.ReadyService().evaluate(
        session=db, workspace_id=ctx.workspace_id, product_id=product.id
    )

    return ok(
        SkuDetail(
            product_id=product.id,
            internal_sku=product.internal_sku,
            batch_id=product.batch_id,
            revision_id=revision.id,
            revision_status=revision.status,
            title_text=concept.title_text if concept else None,
            brand_name=concept.brand_name if concept else None,
            object=concept.object if concept else None,
            core_hash=concept.core_hash if concept else None,
            images=images,
            ready_gate=ReadyGateView(
                ready=gate.ready,
                blockers=gate.blockers,
                passed_count=gate.passed_count,
                required_status=gate.required_status,
            ),
            created_at=product.created_at,
        ).model_dump()
    )


@router.post("/{product_id}/ready", summary="标记 READY_FOR_PUBLISH")
async def mark_ready(
    product_id: str,
    payload: ReadyRequest,
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    begin(
        db,
        workspace_id=ctx.workspace_id,
        operation_key=payload.operation_key,
        scope="product.ready",
        payload={"product_id": product_id},
    )
    try:
        result = ready_service.ReadyService().mark_ready(
            session=db,
            workspace_id=ctx.workspace_id,
            product_id=product_id,
            operation_key=payload.operation_key,
        )
        db.commit()
    except Exception:
        db.rollback()
        raise

    complete(
        db,
        workspace_id=ctx.workspace_id,
        operation_key=payload.operation_key,
        scope="product.ready",
        response_snapshot=result,
    )
    db.commit()
    return ok(ReadyResponse(**result).model_dump())


@router.post("/{product_id}/product-data", summary="构建/刷新商品属性数据")
async def build_product_data(
    product_id: str,
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    revision = _active_revision(db, ctx.workspace_id, product_id)
    if revision is None:
        raise NotFoundError(detail="无可用修订")

    summary = revision_qa_service.RevisionQAService().summarise(
        session=db, workspace_id=ctx.workspace_id, revision_id=revision.id
    )
    record = product_data_service.build_or_refresh(
        session=db,
        workspace_id=ctx.workspace_id,
        revision=revision,
        qa_snapshot={"passed": summary.passed_count, "failed": summary.failed_count, "pending": summary.pending_count},
    )
    db.commit()
    return ok(
        {
            "id": record.id,
            "schema_id": record.schema_id,
            "schema_version": record.schema_version,
            "schema_hash": record.schema_hash,
            "data": record.data,
        }
    )


@router.post("/{product_id}/summarise-qa", summary="汇总修订级 QA")
async def summarise_qa(
    product_id: str,
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    revision = _active_revision(db, ctx.workspace_id, product_id)
    if revision is None:
        raise NotFoundError(detail="无可用修订")

    summary = revision_qa_service.RevisionQAService().summarise(
        session=db, workspace_id=ctx.workspace_id, revision_id=revision.id
    )
    db.commit()
    return ok(
        {
            "revision_id": summary.revision_id,
            "result": summary.result,
            "passed_count": summary.passed_count,
            "failed_count": summary.failed_count,
            "pending_count": summary.pending_count,
            "required_role_status": summary.required_role_status,
        }
    )


def _active_revision(db: Session, workspace_id: str, product_id: str) -> ProductRevision | None:
    rows = db.scalars(
        select(ProductRevision)
        .where(ProductRevision.workspace_id == workspace_id, ProductRevision.product_id == product_id)
        .order_by(ProductRevision.revision_number.desc())
    ).all()
    return rows[0] if rows else None


def _latest_asset(db: Session, image_job_id: str) -> ImageAsset | None:
    return db.scalar(
        select(ImageAsset)
        .join(ImageAttempt, ImageAsset.attempt_id == ImageAttempt.id)
        .where(ImageAttempt.image_job_id == image_job_id)
        .order_by(ImageAsset.created_at.desc())
    )


def _brief(db: Session, asset_id: str, kind: str) -> dict | None:
    qa = image_qa_service.ImageQAService.latest_by_kind(session=db, asset_id=asset_id, kind=kind)
    if qa is None:
        return None
    return {
        "result": qa.result,
        "reason_code": qa.reason_code,
        "reason_detail": qa.reason_detail,
        "evaluated_at": qa.evaluated_at.isoformat() if qa.evaluated_at else None,
    }


