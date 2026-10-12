"""图片 ingest + 技术 QA 测试。"""

from __future__ import annotations

import io

import pytest
from PIL import Image

from app.core.exceptions import ChecksumMismatchError, UnsupportedImageFormatError
from app.core.hashing import sha256_hex
from app.models.image import ImageAsset, ImageQA
from app.models.product import Product, ProductRevision
from app.services import batch_service, sku_service
from app.services.batch_service import CreateBatchCommand
from app.services.image_qa_service import ImageQAService, KIND_SEMANTIC, KIND_TECHNICAL
from app.services.uuid_provider import new_uuid
from app.services.unified_image_ingest_service import IngestCommand, ingest_png


def _png_bytes(*, width: int = 1254, height: int = 1254, transparent: bool = False) -> bytes:
    mode = "RGBA" if transparent else "RGB"
    image = Image.new(mode, (width, height), (255, 255, 255, 0 if transparent else 255))
    buffer = io.BytesIO()
    image.save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def revision_with_jobs(session, workspace_id, user_id):
    sku_service.create_config(
        session=session,
        workspace_id=workspace_id,
        product_type_code="UV_DTF",
        display_name="定制水晶标",
        prefix="DZUVDTF",
    )
    from app.models.title import TitleAsset

    for index in range(10):
        session.add(
            TitleAsset(
                id=new_uuid(),
                title_text=f"Custom UV DTF Transfer Stickers for Small Business Packaging #{index}",
                editorial_status="CONTENT_QUALITY_APPROVED",
                pool_version="1.3.0",
                source_sha="0" * 64,
                source_manifest_id=f"m-{index}",
                query_id=f"Q{index:03d}",
            )
        )
    session.flush()

    command = CreateBatchCommand(
        workspace_id=workspace_id,
        product_type_code="UV_DTF",
        usage_code="small_business_packaging",
        quantity=1,
        image_generation_route="CODEX",
        style_code=None,
        palette_code=None,
        request_key=f"req-{new_uuid()}",
        operation_key=new_uuid(),
        created_by_user_id=user_id,
    )
    batch = batch_service.create_batch(session=session, command=command)
    session.flush()

    from app.services.batch_preparation_service import BatchProductionPreparationService

    BatchProductionPreparationService().prepare_batch(
        session=session, workspace_id=workspace_id, batch_id=batch.id, operation_key=new_uuid()
    )
    session.flush()

    product = session.query(Product).filter(Product.batch_id == batch.id).first()
    revision = (
        session.query(ProductRevision)
        .filter(ProductRevision.product_id == product.id)
        .order_by(ProductRevision.revision_number.desc())
        .first()
    )
    return revision


def test_ingest_valid_png_passes_technical(session, revision_with_jobs):
    data = _png_bytes()
    result = ingest_png(
        session=session,
        command=IngestCommand(
            workspace_id=revision_with_jobs.workspace_id,
            revision_id=revision_with_jobs.id,
            slot=1,
            executor_kind="API",
            executor_id="test",
            provider=None,
            model=None,
            operation_key=new_uuid(),
        ),
        data=data,
        declared_sha256=sha256_hex(data),
    )
    assert result.asset.integrity_state == "VERIFIED"
    assert result.asset.width == 1254
    assert result.technical_qa.result == "PASS"
    # PRD 8.2：语义不确定按失败标记（REVIEW_REQUIRED_UNCERTAIN），强制人工复审，人工可推翻
    assert result.semantic_qa.result == "FAIL"
    assert result.semantic_qa.reason_code == "REVIEW_REQUIRED_UNCERTAIN"


def test_non_png_is_rejected(session, revision_with_jobs):
    with pytest.raises(UnsupportedImageFormatError):
        ingest_png(
            session=session,
            command=IngestCommand(
                workspace_id=revision_with_jobs.workspace_id,
                revision_id=revision_with_jobs.id,
                slot=2,
                executor_kind="API",
                executor_id="test",
                provider=None,
                model=None,
                operation_key=new_uuid(),
            ),
            data=b"\x89PNG\r\n\x1a\nfake",  # PNG magic 但无法解码
        )


def test_checksum_mismatch_is_rejected(session, revision_with_jobs):
    data = _png_bytes()
    with pytest.raises(ChecksumMismatchError):
        ingest_png(
            session=session,
            command=IngestCommand(
                workspace_id=revision_with_jobs.workspace_id,
                revision_id=revision_with_jobs.id,
                slot=3,
                executor_kind="API",
                executor_id="test",
                provider=None,
                model=None,
                operation_key=new_uuid(),
            ),
            data=data,
            declared_sha256="f" * 64,
        )


def test_transparent_png_fails_technical(session, revision_with_jobs):
    data = _png_bytes(transparent=True)
    result = ingest_png(
        session=session,
        command=IngestCommand(
            workspace_id=revision_with_jobs.workspace_id,
            revision_id=revision_with_jobs.id,
            slot=4,
            executor_kind="API",
            executor_id="test",
            provider=None,
            model=None,
            operation_key=new_uuid(),
        ),
        data=data,
    )
    assert result.technical_qa.result == "FAIL"
    assert result.technical_qa.reason_code == "TRANSPARENCY"


def test_undersized_image_fails_technical(session, revision_with_jobs):
    data = _png_bytes(width=512, height=512)
    result = ingest_png(
        session=session,
        command=IngestCommand(
            workspace_id=revision_with_jobs.workspace_id,
            revision_id=revision_with_jobs.id,
            slot=5,
            executor_kind="API",
            executor_id="test",
            provider=None,
            model=None,
            operation_key=new_uuid(),
        ),
        data=data,
    )
    assert result.technical_qa.result == "FAIL"
    assert result.technical_qa.reason_code == "DIMENSION_MISMATCH"


def test_non_square_image_fails_technical(session, revision_with_jobs):
    data = _png_bytes(width=1400, height=1200)
    result = ingest_png(
        session=session,
        command=IngestCommand(
            workspace_id=revision_with_jobs.workspace_id,
            revision_id=revision_with_jobs.id,
            slot=6,
            executor_kind="API",
            executor_id="test",
            provider=None,
            model=None,
            operation_key=new_uuid(),
        ),
        data=data,
    )
    assert result.technical_qa.result == "FAIL"


def test_qa_records_are_append_only(session, revision_with_jobs):
    data = _png_bytes()
    result = ingest_png(
        session=session,
        command=IngestCommand(
            workspace_id=revision_with_jobs.workspace_id,
            revision_id=revision_with_jobs.id,
            slot=7,
            executor_kind="API",
            executor_id="test",
            provider=None,
            model=None,
            operation_key=new_uuid(),
        ),
        data=data,
    )
    first_count = session.query(ImageQA).filter(ImageQA.asset_id == result.asset.id).count()
    ImageQAService().run_technical_qa(
        session=session,
        asset=result.asset,
        job=result.job,
        operation_key=new_uuid(),
        source_bytes=data,
    )
    second_count = session.query(ImageQA).filter(ImageQA.asset_id == result.asset.id).count()
    assert second_count > first_count
    assert session.query(ImageAsset).filter(ImageAsset.id == result.asset.id).one().integrity_state == "VERIFIED"


def test_asset_stores_key_not_absolute_path(session, revision_with_jobs):
    data = _png_bytes()
    result = ingest_png(
        session=session,
        command=IngestCommand(
            workspace_id=revision_with_jobs.workspace_id,
            revision_id=revision_with_jobs.id,
            slot=8,
            executor_kind="API",
            executor_id="test",
            provider=None,
            model=None,
            operation_key=new_uuid(),
        ),
        data=data,
    )
    assert not result.asset.storage_key.startswith("/")
    assert ":" not in result.asset.storage_key
    assert result.asset.storage_key.endswith(".png")
    assert KIND_TECHNICAL == "TECHNICAL"
    assert KIND_SEMANTIC == "SEMANTIC"
