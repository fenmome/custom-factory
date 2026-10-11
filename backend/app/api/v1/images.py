"""图片接口（统一接收 + 读取 + 初审 / OCR）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, File, Header, Query, UploadFile
from fastapi.responses import Response
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.exceptions import ImageJobNotFoundError, ImageAssetNotFoundError
from app.core.resource_loader import image_policy
from app.core.response import ok
from app.core.storage import storage
from app.deps import CurrentContext, get_current_context, require_operator
from app.models.image import ImageAsset, ImageAttempt, ImageJob
from app.schemas.image import ImageUploadResponse, QaBrief
from app.services import ocr_text_qa_service, unified_image_ingest_service
from app.services.unified_image_ingest_service import IngestCommand

router = APIRouter()


def _resolve_job(*, db: Session, workspace_id: str, revision_id: str, slot: int) -> ImageJob:
    job = db.scalar(
        select(ImageJob).where(
            ImageJob.workspace_id == workspace_id,
            ImageJob.revision_id == revision_id,
            ImageJob.slot == slot,
        )
    )
    if job is None:
        raise ImageJobNotFoundError(detail=f"revision={revision_id} slot={slot}")
    return job


@router.post("/{revision_id}/slots/{slot}", summary="上传槽位图片（仅 PNG，原样写入）")
async def upload_image(
    revision_id: str,
    slot: int,
    file: UploadFile = File(...),
    expected_sha256: str | None = Header(default=None, alias="X-Content-Sha256"),
    model: str | None = Header(default=None, alias="X-Image-Model"),
    provider: str | None = Header(default=None, alias="X-Image-Provider"),
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    _resolve_job(db=db, workspace_id=ctx.workspace_id, revision_id=revision_id, slot=slot)

    data = await file.read()
    if not data:
        raise ImageAssetNotFoundError(detail="上传内容为空")

    result = unified_image_ingest_service.ingest_png(
        session=db,
        command=IngestCommand(
            workspace_id=ctx.workspace_id,
            revision_id=revision_id,
            slot=slot,
            executor_kind="API",
            executor_id=f"user:{ctx.user_id}",
            provider=provider,
            model=model,
            operation_key=f"web:{revision_id}:{slot}",
        ),
        data=data,
        declared_sha256=expected_sha256,
    )
    db.commit()

    return ok(
        ImageUploadResponse(
            slot=slot,
            role=result.job.role,
            job_state=result.job.state,
            attempt_id=result.attempt.id,
            asset_id=result.asset.id,
            storage_key=result.asset.storage_key,
            checksum=result.asset.checksum_digest,
            byte_size=result.asset.byte_size,
            width=result.asset.width,
            height=result.asset.height,
            technical=QaBrief(
                result=result.technical_qa.result,
                reason_code=result.technical_qa.reason_code,
                reason_detail=result.technical_qa.reason_detail,
            ),
            semantic=QaBrief(
                result=result.semantic_qa.result,
                reason_code=result.semantic_qa.reason_code,
                reason_detail=result.semantic_qa.reason_detail,
            ),
        ).model_dump()
    )


@router.get("/assets/{asset_id}/raw", summary="读取图片原始字节（只读，禁止转换）")
async def read_raw(
    asset_id: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    asset = db.scalar(
        select(ImageAsset).where(ImageAsset.workspace_id == ctx.workspace_id, ImageAsset.id == asset_id)
    )
    if asset is None:
        raise ImageAssetNotFoundError

    data = storage.read_bytes(key=asset.storage_key)
    return Response(content=data, media_type=asset.mime_type)


@router.post("/assets/{asset_id}/ocr", summary="对该图片执行 OCR 文字质检")
async def run_ocr(
    asset_id: str,
    ctx: CurrentContext = Depends(require_operator),
    db: Session = Depends(get_session),
):
    asset = db.scalar(
        select(ImageAsset).where(ImageAsset.workspace_id == ctx.workspace_id, ImageAsset.id == asset_id)
    )
    if asset is None:
        raise ImageAssetNotFoundError
    job = db.get(ImageJob, asset.image_job_id)
    if job is None:
        raise ImageJobNotFoundError

    record = ocr_text_qa_service.OCRTextQAService().evaluate(
        session=db, asset=asset, job=job, operation_key=f"web:ocr:{asset_id}"
    )
    db.commit()
    return ok(
        {
            "asset_id": asset_id,
            "result": record.result,
            "reason_code": record.reason_code,
            "reason_detail": record.reason_detail,
        }
    )


@router.get("/policy", summary="当前图片策略（从资源文件加载）")
async def get_policy(_: CurrentContext = Depends(get_current_context)):
    resource = image_policy()
    return ok(
        {
            "policy_id": resource.data["policy_id"],
            "version": resource.data["version"],
            "content_hash": resource.content_hash,
            "policy": resource.data,
        }
    )


@router.get("/jobs", summary="某修订的槽位任务列表")
async def list_jobs(
    revision_id: str = Query(...),
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    jobs = db.scalars(
        select(ImageJob)
        .where(ImageJob.workspace_id == ctx.workspace_id, ImageJob.revision_id == revision_id)
        .order_by(ImageJob.slot)
    ).all()
    items = []
    for job in jobs:
        asset = db.scalar(
            select(ImageAsset)
            .join(ImageAttempt, ImageAsset.attempt_id == ImageAttempt.id)
            .where(ImageAttempt.image_job_id == job.id)
            .order_by(ImageAsset.created_at.desc())
        )
        items.append(
            {
                "slot": job.slot,
                "role": job.role,
                "is_required": job.is_required,
                "state": job.state,
                "asset_id": asset.id if asset else None,
                "checksum": asset.checksum_digest if asset else None,
            }
        )
    return ok({"revision_id": revision_id, "items": items})
