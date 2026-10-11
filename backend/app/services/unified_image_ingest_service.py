"""统一图片接收服务（API 路线 / Codex 路线共用）。

顺序：
1. 校验必须是 PNG（非 PNG 直接拒绝，禁止转换）
2. 校验上传字节 SHA-256 与声明一致
3. 原样写入存储（禁止缩放/裁剪/压缩）
4. 注册 ImageAsset（integrity_state = VERIFIED）
5. 触发技术 QA + 语义 QA
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import IMAGE_ASSET_REGISTERED, record_event, utc_now
from app.core.exceptions import (
    ChecksumMismatchError,
    ImageJobNotFoundError,
    StorageWriteError,
    UnsupportedImageFormatError,
)
from app.core.hashing import sha256_hex
from app.core.image_inspector import probe, sniff_is_png
from app.core.resource_loader import image_policy
from app.core.storage import storage
from app.models.image import ImageAsset, ImageAttempt, ImageJob, ImageQA
from app.models.product import ProductRevision
from app.services import image_qa_service
from app.services.image_storage_key_service import build_storage_key
from app.services.uuid_provider import new_uuid


@dataclass(frozen=True)
class IngestCommand:
    workspace_id: str
    revision_id: str
    slot: int
    executor_kind: str
    executor_id: str
    provider: str | None
    model: str | None
    operation_key: str


@dataclass(frozen=True)
class IngestResult:
    job: ImageJob
    attempt: ImageAttempt
    asset: ImageAsset
    technical_qa: ImageQA
    semantic_qa: ImageQA


def ingest_png(
    *,
    session: Session,
    command: IngestCommand,
    data: bytes,
    declared_sha256: str | None = None,
) -> IngestResult:
    if not sniff_is_png(data):
        raise UnsupportedImageFormatError(detail="仅接受 PNG，禁止任何格式转换")

    actual_sha = sha256_hex(data)
    if declared_sha256 and declared_sha256.lower() != actual_sha:
        raise ChecksumMismatchError(detail=f"声明={declared_sha256} 实际={actual_sha}")

    job = session.scalar(
        select(ImageJob).where(
            ImageJob.workspace_id == command.workspace_id,
            ImageJob.revision_id == command.revision_id,
            ImageJob.slot == command.slot,
        )
    )
    if job is None:
        raise ImageJobNotFoundError(detail=f"revision={command.revision_id} slot={command.slot}")

    revision = session.get(ProductRevision, command.revision_id)
    if revision is None:
        raise ImageJobNotFoundError(detail=f"revision={command.revision_id}")

    info = probe(data)
    if not info.is_png or not info.readable:
        raise UnsupportedImageFormatError(detail=info.error or "PNG 解码失败")

    storage_key = build_storage_key(
        prefix=_prefix_of(session=session, revision_id=command.revision_id),
        sku=_sku_of(session=session, revision_id=command.revision_id),
        slot=command.slot,
        revision_number=revision.revision_number,
        revision_id=revision.id,
    )

    try:
        storage.put(key=storage_key, data=data, overwrite=True)
    except StorageWriteError:
        raise

    attempt = ImageAttempt(
        id=new_uuid(),
        workspace_id=command.workspace_id,
        image_job_id=job.id,
        attempt_number=_next_attempt_number(session=session, image_job_id=job.id),
        state="SUCCEEDED",
        provider=command.provider,
        model=command.model,
        prompt_version=str(image_policy()["version"]),
        prompt_source_hash=job.prompt_source_hash,
        rendered_prompt=job.rendered_prompt,
        settled_at=utc_now(),
    )
    session.add(attempt)
    session.flush()

    asset = ImageAsset(
        id=new_uuid(),
        workspace_id=command.workspace_id,
        attempt_id=attempt.id,
        image_job_id=job.id,
        provenance_kind="GENERATED",
        integrity_state="VERIFIED",
        storage_profile=storage.profile,
        storage_key=storage_key,
        checksum_algorithm="sha256",
        checksum_digest=actual_sha,
        byte_size=len(data),
        width=info.width,
        height=info.height,
        mime_type="image/png",
    )
    session.add(asset)
    session.flush()

    job.state = "ASSET_RECORDED"
    session.flush()

    record_event(
        session,
        workspace_id=command.workspace_id,
        entity_type="IMAGE_ASSET",
        entity_id=asset.id,
        event_kind=IMAGE_ASSET_REGISTERED,
        payload={
            "slot": command.slot,
            "storage_key": storage_key,
            "sha256": actual_sha,
            "size": len(data),
            "width": info.width,
            "height": info.height,
        },
    )

    qa_service = image_qa_service.ImageQAService()
    technical = qa_service.run_technical_qa(
        session=session,
        asset=asset,
        job=job,
        operation_key=f"{command.operation_key}:tech",
        source_bytes=data,
    )
    semantic = qa_service.run_semantic_qa(
        session=session,
        asset=asset,
        job=job,
        operation_key=f"{command.operation_key}:sem",
    )
    session.flush()

    return IngestResult(job=job, attempt=attempt, asset=asset, technical_qa=technical, semantic_qa=semantic)


def _next_attempt_number(*, session: Session, image_job_id: str) -> int:
    from sqlalchemy import func

    used = session.scalar(
        select(func.count()).select_from(ImageAttempt).where(ImageAttempt.image_job_id == image_job_id)
    )
    return int(used or 0) + 1


def _sku_of(*, session: Session, revision_id: str) -> str:
    from app.models.product import Product

    revision = session.get(ProductRevision, revision_id)
    if revision is None:
        return "UNKNOWN"
    product = session.get(Product, revision.product_id)
    return product.internal_sku if product else "UNKNOWN"


def _prefix_of(*, session: Session, revision_id: str) -> str:
    from app.models.product import Product

    revision = session.get(ProductRevision, revision_id)
    if revision is None:
        return "UNKNOWN"
    product = session.get(Product, revision.product_id)
    return product.allocated_prefix if product else "UNKNOWN"
