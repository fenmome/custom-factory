"""端到端链路测试：批次 → QA → 复审 → READY。"""

from __future__ import annotations

import io

import pytest
from PIL import Image
from sqlalchemy import select

from app.core.exceptions import ReadyGateBlockedError
from app.core.events import REVISION_READY, list_events
from app.models.image import ImageAsset, ImageAttempt, ImageJob, ImageQA
from app.models.product import ListingConcept, Product, ProductRevision
from app.models.title import TitleAsset
from app.services import (
    ocr_text_qa_service,
    product_data_service,
    ready_service,
    revision_qa_service,
    sku_service,
)
from app.services.batch_service import CreateBatchCommand
from app.services.batch_preparation_service import BatchProductionPreparationService
from app.services.batch_service import create_batch
from app.services.qa_review_service import QAReviewService, ReviewDecision, SubmitReviewCommand
from app.services.unified_image_ingest_service import IngestCommand, ingest_png
from app.services.uuid_provider import new_uuid

PASSING_SLOTS = (1, 2, 3, 4, 6)


def _png(width: int = 1254, height: int = 1254) -> bytes:
    buffer = io.BytesIO()
    Image.new("RGB", (width, height), (255, 255, 255)).save(buffer, format="PNG")
    return buffer.getvalue()


@pytest.fixture()
def batch_with_products(session, workspace_id, user_id):
    sku_service.create_config(
        session=session,
        workspace_id=workspace_id,
        product_type_code="UV_DTF",
        display_name="定制水晶标",
        prefix="DZUVDTF",
    )
    for index in range(5):
        session.add(
            TitleAsset(
                id=new_uuid(),
                title_text=f"Custom UV DTF Transfer Stickers for Small Business Packaging #{index}",
                editorial_status="CONTENT_QUALITY_APPROVED",
                pool_version="1.3.0",
                source_sha="0" * 64,
                source_manifest_id=f"m-{index}",
            )
        )
    session.flush()

    batch = create_batch(
        session=session,
        command=CreateBatchCommand(
            workspace_id=workspace_id,
            product_type_code="UV_DTF",
            usage_code="small_business_packaging",
            quantity=2,
            image_generation_route="CODEX",
            style_code=None,
            palette_code=None,
            request_key=f"req-{new_uuid()}",
            operation_key=new_uuid(),
            created_by_user_id=user_id,
        ),
    )
    session.flush()
    BatchProductionPreparationService().prepare_batch(
        session=session, workspace_id=workspace_id, batch_id=batch.id, operation_key=new_uuid()
    )
    session.flush()
    return batch


def _products(session, workspace_id, batch_id):
    return list(
        session.scalars(
            select(Product).where(Product.workspace_id == workspace_id, Product.batch_id == batch_id)
        ).all()
    )


def _fill_slot(session, workspace_id, revision_id, slot: int, png: bytes):
    return ingest_png(
        session=session,
        command=IngestCommand(
            workspace_id=workspace_id,
            revision_id=revision_id,
            slot=slot,
            executor_kind="API",
            executor_id="e2e",
            provider=None,
            model=None,
            operation_key=new_uuid(),
        ),
        data=png,
    )


def test_sku_allocation_is_contiguous_across_batch(session, workspace_id, batch_with_products):
    products = _products(session, workspace_id, batch_with_products.id)
    skus = sorted(p.internal_sku for p in products)
    assert skus == ["DZUVDTF000001", "DZUVDTF000002"]
    sequences = sorted(p.allocated_sequence for p in products)
    assert sequences == [1, 2]


def test_revision_and_concept_created(session, workspace_id, batch_with_products):
    product = _products(session, workspace_id, batch_with_products.id)[0]
    revision = session.scalar(
        select(ProductRevision).where(ProductRevision.product_id == product.id)
    )
    concept = session.get(ListingConcept, revision.concept_id)
    assert concept is not None
    assert concept.state == "FROZEN"
    assert concept.brand_name
    assert concept.core_hash
    assert concept.surface_gate == [
        "clean",
        "dry",
        "smooth",
        "hard",
        "non_porous",
        "external_surface",
    ]


def test_plan_frozen_and_image_jobs_ready(session, workspace_id, batch_with_products):
    from app.services.frozen_sku_plan_store import FrozenSkuPlanStore

    product = _products(session, workspace_id, batch_with_products.id)[0]
    revision = session.scalar(
        select(ProductRevision).where(ProductRevision.product_id == product.id)
    )

    store = FrozenSkuPlanStore()
    plan = store.load(workspace_id=workspace_id, revision_id=revision.id)
    assert plan is not None
    assert store.verify(workspace_id=workspace_id, revision_id=revision.id)

    package = plan["package"]
    assert package["plan_format"] == "codex-image-task-v1"
    assert package["internal_sku"] == product.internal_sku
    assert package["core_hash"] == session.get(ListingConcept, revision.concept_id).core_hash
    assert len(package["jobs"]) == 8
    for job in package["jobs"]:
        assert job["prompt"]

    jobs = session.scalars(
        select(ImageJob).where(ImageJob.revision_id == revision.id).order_by(ImageJob.slot)
    ).all()
    assert len(jobs) == 8
    assert all(job.state == "PLANNED" for job in jobs)
    assert all(job.rendered_prompt for job in jobs)
    assert [job.slot for job in jobs if job.is_required] == [1, 2, 3]


def test_ready_gate_blocks_before_images(session, workspace_id, batch_with_products):
    product = _products(session, workspace_id, batch_with_products.id)[0]
    gate = ready_service.ReadyService().evaluate(
        session=session, workspace_id=workspace_id, product_id=product.id
    )
    assert not gate.ready
    assert any("READY_COUNT_BELOW_MIN" in b or "REQUIRED_ROLE" in b for b in gate.blockers)


def test_full_path_to_ready_with_human_review(session, workspace_id, batch_with_products, user_id):
    product = _products(session, workspace_id, batch_with_products.id)[0]
    revision = session.scalar(
        select(ProductRevision).where(ProductRevision.product_id == product.id)
    )

    # 1) 上传必备槽位图片（自动+手动混合）
    for slot in PASSING_SLOTS:
        result = _fill_slot(session, workspace_id, revision.id, slot, _png())
        assert result.technical_qa.result == "PASS"
        ocr_text_qa_service.OCRTextQAService().evaluate(
            session=session, asset=result.asset, job=result.job, operation_key=new_uuid()
        )
    session.flush()

    # 2) 汇总修订级 QA（语义不确定按 FAIL 标记 → 修订级失败，等待人工推翻）
    summary = revision_qa_service.RevisionQAService().summarise(
        session=session, workspace_id=workspace_id, revision_id=revision.id
    )
    session.flush()
    assert summary.result == "FAIL"
    assert summary.failed_count >= 5

    # 3) 人工复审：语义由人工做最终裁定
    view = QAReviewService().build_review_view(
        session=session, workspace_id=workspace_id, product_id=product.id
    )
    decisions = [
        ReviewDecision(slot=item["slot"], decision="PASS")
        for item in view["items"]
        if item.get("asset_id") and item["slot"] in PASSING_SLOTS
    ]
    review_result = QAReviewService().submit(
        session=session,
        command=SubmitReviewCommand(
            workspace_id=workspace_id,
            product_id=product.id,
            operation_key=new_uuid(),
            reviewer_id=user_id,
            decisions=decisions,
            snapshot=view["snapshot"],
            complete_set=False,
        ),
    )
    session.flush()
    assert review_result["reviewed_count"] == len(PASSING_SLOTS)
    assert review_result["rejected"] == []

    # 5) 人工复审后重新汇总 → 变为 PASS
    summary = revision_qa_service.RevisionQAService().summarise(
        session=session, workspace_id=workspace_id, revision_id=revision.id
    )
    session.flush()
    assert summary.result == "PASS"
    assert summary.passed_count >= 5

    # 6) 构建商品属性数据（绑定当前 QA 指纹）
    data = product_data_service.build_or_refresh(
        session=session,
        workspace_id=workspace_id,
        revision=revision,
        qa_snapshot={
            "passed": summary.passed_count,
            "failed": summary.failed_count,
            "pending": summary.pending_count,
            "required_role_status": summary.required_role_status,
        },
    )
    session.flush()
    assert data.data == {
        "surface_gate": [
            "clean",
            "dry",
            "smooth",
            "hard",
            "non_porous",
            "external_surface",
        ]
    }

    # 7) READY 门禁
    ready_service.ReadyService().mark_ready(
        session=session,
        workspace_id=workspace_id,
        product_id=product.id,
        operation_key=new_uuid(),
    )
    session.flush()

    session.refresh(revision)
    assert revision.status == "READY_FOR_PUBLISH"
    assert revision.ready_gate_id

    events = list_events(session, workspace_id=workspace_id, entity_id=revision.id)
    assert any(e.event_kind == REVISION_READY for e in events)


def test_hard_technical_failure_cannot_be_human_passed(session, workspace_id, batch_with_products, user_id):
    product = _products(session, workspace_id, batch_with_products.id)[1]
    revision = session.scalar(
        select(ProductRevision).where(ProductRevision.product_id == product.id)
    )

    # 上传透明 PNG → 硬技术失败 TRANSPARENCY
    buffer = io.BytesIO()
    Image.new("RGBA", (1254, 1254), (255, 255, 255, 0)).save(buffer, format="PNG")
    result = _fill_slot(session, workspace_id, revision.id, 1, buffer.getvalue())
    assert result.technical_qa.result == "FAIL"
    assert result.technical_qa.reason_code == "TRANSPARENCY"

    view = QAReviewService().build_review_view(
        session=session, workspace_id=workspace_id, product_id=product.id
    )
    review_result = QAReviewService().submit(
        session=session,
        command=SubmitReviewCommand(
            workspace_id=workspace_id,
            product_id=product.id,
            operation_key=new_uuid(),
            reviewer_id=user_id,
            decisions=[ReviewDecision(slot=1, decision="PASS")],
            snapshot=view["snapshot"],
        ),
    )
    assert review_result["accepted"] == []
    assert len(review_result["rejected"]) == 1
    assert "TRANSPARENCY" in review_result["rejected"][0]["detail"]


def test_human_fail_requires_reason_code(session, workspace_id, batch_with_products, user_id):
    product = _products(session, workspace_id, batch_with_products.id)[1]
    _fill_slot(
        session,
        workspace_id,
        session.scalar(select(ProductRevision).where(ProductRevision.product_id == product.id)).id,
        1,
        _png(),
    )
    session.flush()

    view = QAReviewService().build_review_view(
        session=session, workspace_id=workspace_id, product_id=product.id
    )
    from app.core.exceptions import ValidationError

    with pytest.raises(ValidationError):
        QAReviewService().submit(
            session=session,
            command=SubmitReviewCommand(
                workspace_id=workspace_id,
                product_id=product.id,
                operation_key=new_uuid(),
                reviewer_id=user_id,
                decisions=[ReviewDecision(slot=1, decision="FAIL", reason_code=None)],
                snapshot=view["snapshot"],
            ),
        )


def test_stale_snapshot_is_rejected(session, workspace_id, batch_with_products, user_id):
    from app.core.exceptions import ReviewSnapshotStaleError

    product = _products(session, workspace_id, batch_with_products.id)[1]
    revision = session.scalar(
        select(ProductRevision).where(ProductRevision.product_id == product.id)
    )
    _fill_slot(session, workspace_id, revision.id, 1, _png())
    session.flush()

    asset = session.scalar(
        select(ImageAsset)
        .join(ImageAttempt, ImageAsset.attempt_id == ImageAttempt.id)
        .where(ImageAttempt.image_job_id == session.scalar(
            select(ImageJob.id).where(ImageJob.revision_id == revision.id, ImageJob.slot == 1)
        ))
    )

    from app.services.qa_review_service import ReviewSnapshotItem

    with pytest.raises(ReviewSnapshotStaleError):
        QAReviewService().submit(
            session=session,
            command=SubmitReviewCommand(
                workspace_id=workspace_id,
                product_id=product.id,
                operation_key=new_uuid(),
                reviewer_id=user_id,
                decisions=[],
                snapshot=[ReviewSnapshotItem(asset_id=asset.id, checksum="stale")],
            ),
        )


def test_ready_is_blocked_when_requirements_unmet(session, workspace_id, batch_with_products):
    product = _products(session, workspace_id, batch_with_products.id)[1]
    with pytest.raises(ReadyGateBlockedError):
        ready_service.ReadyService().mark_ready(
            session=session,
            workspace_id=workspace_id,
            product_id=product.id,
            operation_key=new_uuid(),
        )
