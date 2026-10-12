"""人工复审服务（FR-08.3）。

规则：
- 粒度：按 SKU 集合（一次审核 8 张图）
- 追加式记录（kind=HUMAN，只 INSERT）
- 人工 PASS 可推翻语义自动 FAIL；人工 FAIL 可推翻语义自动 PASS
- **硬技术失败永远不可人工放行**
- 反转自动结果必须选择原因码；`OTHER` 需填写说明
- 并发保护：快照校验，stale snapshot 拒绝
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import HUMAN_REVIEW_SUBMITTED, record_event, utc_now
from app.core.exceptions import HumanReviewRejected, ReviewSnapshotStaleError, ValidationError
from app.core.resource_loader import load_resource
from app.models.image import ImageAsset, ImageJob, ImageQA
from app.models.product import ListingConcept, Product, ProductRevision
from app.services import image_qa_service, revision_qa_service
from app.services.uuid_provider import new_uuid

REVIEW_RULE_PATH = "image_policy/uv_dtf_image_policy_v1_2.json"

REVIEW_REASON_CODES = (
    "PRODUCT_MISMATCH",
    "ROLE_MISMATCH",
    "CONCEPT_INCONSISTENCY",
    "TEXT_ERROR",
    "VISUAL_DEFECT",
    "OTHER",
)


@dataclass(frozen=True)
class ReviewDecision:
    slot: int
    decision: str  # PASS | FAIL
    reason_code: str | None = None
    note: str | None = None


@dataclass(frozen=True)
class ReviewSnapshotItem:
    asset_id: str
    checksum: str


@dataclass(frozen=True)
class SubmitReviewCommand:
    workspace_id: str
    product_id: str
    operation_key: str
    reviewer_id: str
    decisions: list[ReviewDecision] = field(default_factory=list)
    snapshot: list[ReviewSnapshotItem] = field(default_factory=list)
    complete_set: bool = False


class QAReviewService:
    def __init__(self, *, qa_service: image_qa_service.ImageQAService | None = None) -> None:
        self.qa_service = qa_service or image_qa_service.ImageQAService()

    # ---------------- 读取视图 ----------------
    def build_review_view(self, *, session: Session, workspace_id: str, product_id: str) -> dict:
        product = session.scalar(
            select(Product).where(Product.workspace_id == workspace_id, Product.id == product_id)
        )
        if product is None:
            raise ValidationError(detail=f"product_id={product_id} 不存在")

        revision = self._active_revision(session=session, workspace_id=workspace_id, product_id=product_id)
        if revision is None:
            raise ValidationError(detail=f"product_id={product_id} 无修订")

        concept = session.get(ListingConcept, revision.concept_id)
        jobs = session.scalars(
            select(ImageJob)
            .where(ImageJob.workspace_id == workspace_id, ImageJob.revision_id == revision.id)
            .order_by(ImageJob.slot)
        ).all()

        items: list[dict] = []
        for job in jobs:
            asset = self._latest_asset(session=session, image_job_id=job.id)
            if asset is None:
                items.append(_empty_item(job=job))
                continue
            technical = image_qa_service.ImageQAService.latest_by_kind(
                session=session, asset_id=asset.id, kind=image_qa_service.KIND_TECHNICAL
            )
            semantic = image_qa_service.ImageQAService.latest_by_kind(
                session=session, asset_id=asset.id, kind=image_qa_service.KIND_SEMANTIC
            )
            human = image_qa_service.ImageQAService.latest_by_kind(
                session=session, asset_id=asset.id, kind=image_qa_service.KIND_HUMAN
            )
            ocr = image_qa_service.ImageQAService.latest_by_kind(
                session=session, asset_id=asset.id, kind=image_qa_service.KIND_OCR
            )
            items.append(
                {
                    "slot": job.slot,
                    "role": job.role,
                    "is_required": job.is_required,
                    "asset_id": asset.id,
                    "checksum": asset.checksum_digest,
                    "width": asset.width,
                    "height": asset.height,
                    "byte_size": asset.byte_size,
                    "integrity_state": asset.integrity_state,
                    "technical": _qa_brief(technical),
                    "semantic": _qa_brief(semantic),
                    "human": _qa_brief(human),
                    "ocr": _qa_brief(ocr),
                    "effective": image_qa_service.ImageQAService.effective_result(session=session, asset_id=asset.id),
                    "history": [
                        _qa_brief(row)
                        for row in session.scalars(
                            select(ImageQA)
                            .where(ImageQA.asset_id == asset.id)
                            .order_by(ImageQA.evaluated_at.desc())
                            .limit(20)
                        ).all()
                    ],
                }
            )

        return {
            "product_id": product.id,
            "internal_sku": product.internal_sku,
            "revision_id": revision.id,
            "revision_status": revision.status,
            "brand_name": concept.brand_name if concept else None,
            "object": concept.object if concept else None,
            "title_text": concept.title_text if concept else None,
            "items": items,
            "snapshot": [
                {"asset_id": item["asset_id"], "checksum": item["checksum"]}
                for item in items
                if item.get("asset_id")
            ],
        }

    # ---------------- 提交复审 ----------------
    def submit(self, *, session: Session, command: SubmitReviewCommand) -> dict:
        product = session.scalar(
            select(Product).where(Product.workspace_id == command.workspace_id, Product.id == command.product_id)
        )
        if product is None:
            raise ValidationError(detail=f"product_id={command.product_id} 不存在")

        revision = self._active_revision(
            session=session, workspace_id=command.workspace_id, product_id=command.product_id
        )
        if revision is None:
            raise ValidationError(detail="无可用修订")

        jobs = {
            job.slot: job
            for job in session.scalars(
                select(ImageJob).where(ImageJob.workspace_id == command.workspace_id, ImageJob.revision_id == revision.id)
            ).all()
        }

        self._verify_snapshot(session=session, snapshot=command.snapshot)

        accepted: list[dict] = []
        rejected: list[dict] = []

        for decision in command.decisions:
            job = jobs.get(decision.slot)
            if job is None:
                raise ValidationError(detail=f"槽位 {decision.slot} 不存在")
            asset = self._latest_asset(session=session, image_job_id=job.id)
            if asset is None:
                raise ValidationError(detail=f"槽位 {decision.slot} 尚无资产")

            try:
                record = self._apply_decision(
                    session=session,
                    asset=asset,
                    job=job,
                    decision=decision,
                    command=command,
                )
                accepted.append({"slot": decision.slot, "qa_id": record.id, "result": record.result})
            except HumanReviewRejected as exc:
                rejected.append({"slot": decision.slot, "error": exc.message, "detail": exc.detail})

        session.flush()

        record_event(
            session,
            workspace_id=command.workspace_id,
            entity_type="PRODUCT",
            entity_id=command.product_id,
            event_kind=HUMAN_REVIEW_SUBMITTED,
            payload={
                "accepted": accepted,
                "rejected": rejected,
                "complete_set": command.complete_set,
                "reviewer_id": command.reviewer_id,
            },
        )
        session.flush()

        # 人工裁定后立即重新汇总修订级 QA（同步更新结果并触发 Guard 评估）
        revision = session.scalar(
            select(ProductRevision)
            .where(
                ProductRevision.workspace_id == command.workspace_id,
                ProductRevision.product_id == command.product_id,
            )
            .order_by(ProductRevision.revision_number.desc())
        )
        if revision is not None:
            revision_qa_service.RevisionQAService().summarise(
                session=session, workspace_id=command.workspace_id, revision_id=revision.id
            )

        return {
            "product_id": command.product_id,
            "accepted": accepted,
            "rejected": rejected,
            "reviewed_count": len(accepted),
        }

    # ---------------- 内部 ----------------
    def _apply_decision(
        self,
        *,
        session: Session,
        asset: ImageAsset,
        job: ImageJob,
        decision: ReviewDecision,
        command: SubmitReviewCommand,
    ) -> ImageQA:
        if decision.decision not in {"PASS", "FAIL"}:
            raise ValidationError(detail="decision 仅支持 PASS / FAIL")

        if decision.decision == "PASS":
            technical = image_qa_service.ImageQAService.latest_by_kind(
                session=session, asset_id=asset.id, kind=image_qa_service.KIND_TECHNICAL
            )
            if technical is not None and technical.result == "FAIL":
                code = technical.reason_code or ""
                if image_qa_service.is_hard_technical(code):
                    raise HumanReviewRejected(detail=f"硬技术失败 {code} 不可人工放行")

        if decision.decision == "FAIL":
            if decision.reason_code is None:
                raise ValidationError(detail="标记问题必须选择原因码")
            if decision.reason_code not in REVIEW_REASON_CODES:
                raise ValidationError(detail=f"未知原因码 {decision.reason_code}")
            if decision.reason_code == "OTHER" and not (decision.note or "").strip():
                raise ValidationError(detail="原因码 OTHER 必须填写说明")

        rule = load_resource(relative_path=REVIEW_RULE_PATH)
        record = ImageQA(
            id=new_uuid(),
            workspace_id=asset.workspace_id,
            asset_id=asset.id,
            image_job_id=job.id,
            kind=image_qa_service.KIND_HUMAN,
            result=decision.decision,
            reason_code=decision.reason_code,
            reason_detail=(decision.note or "").strip() or None,
            rule_id=str(rule.data.get("policy_id")),
            rule_version=str(rule.data.get("version")),
            rule_hash=rule.content_hash,
            asset_checksum=asset.checksum_digest,
            operation_key=f"{command.operation_key}:{job.slot}",
            overrides={"reviewer_id": command.reviewer_id},
            evaluated_by=command.reviewer_id,
            evaluated_at=utc_now(),
        )
        session.add(record)
        session.flush()
        return record

    @staticmethod
    def _verify_snapshot(*, session: Session, snapshot: Sequence[ReviewSnapshotItem | dict]) -> None:
        """并发保护：提交的资产校验和必须与页面加载时一致。"""
        if not snapshot:
            return
        for item in snapshot:
            if isinstance(item, dict):
                asset_id = str(item.get("asset_id"))
                checksum = str(item.get("checksum"))
            else:
                asset_id = item.asset_id
                checksum = item.checksum
            current = session.get(ImageAsset, asset_id)
            if current is None or current.checksum_digest != checksum:
                raise ReviewSnapshotStaleError(
                    detail=f"asset {asset_id} 已变化，请刷新页面后重新审核"
                )

    @staticmethod
    def _latest_asset(*, session: Session, image_job_id: str) -> ImageAsset | None:
        from app.models.image import ImageAttempt

        return session.scalar(
            select(ImageAsset)
            .join(ImageAttempt, ImageAsset.attempt_id == ImageAttempt.id)
            .where(ImageAttempt.image_job_id == image_job_id)
            .order_by(ImageAsset.created_at.desc())
        )

    @staticmethod
    def _active_revision(*, session: Session, workspace_id: str, product_id: str) -> ProductRevision | None:
        rows = session.scalars(
            select(ProductRevision)
            .where(ProductRevision.workspace_id == workspace_id, ProductRevision.product_id == product_id)
            .order_by(ProductRevision.revision_number.desc())
        ).all()
        return rows[0] if rows else None


def _qa_brief(qa: ImageQA | None) -> dict | None:
    if qa is None:
        return None
    return {
        "result": qa.result,
        "reason_code": qa.reason_code,
        "reason_detail": qa.reason_detail,
        "evaluated_at": qa.evaluated_at.isoformat() if qa.evaluated_at else None,
    }


def _empty_item(*, job: ImageJob) -> dict:
    return {
        "slot": job.slot,
        "role": job.role,
        "is_required": job.is_required,
        "asset_id": None,
        "checksum": None,
        "width": None,
        "height": None,
        "byte_size": None,
        "integrity_state": None,
        "technical": None,
        "semantic": None,
        "human": None,
        "ocr": None,
        "effective": "PENDING",
        "history": [],
    }
