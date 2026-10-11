"""READY 判定（FR-10 / agent.md 4.5）。

全部满足才可通过：
1. 已分配永久 SKU
2. ListingConcept 状态 FROZEN + 标题身份确认
3. ProductData 存在且 QA 指纹匹配
4. 图片 ≥5 张通过 + 所有必需角色通过
5. 每张选中图片字节完整性 VERIFIED + 当前有效 QA = PASS
6. 原子完成 TitleUsage + Revision 状态 + 审计事件
"""

from __future__ import annotations

from dataclasses import dataclass, field

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import REVISION_READY, record_event, utc_now
from app.core.exceptions import ReadyGateBlockedError
from app.core.resource_loader import image_policy
from app.core.storage import storage
from app.models.image import ImageAsset, ImageAttempt, ImageJob, RevisionQA
from app.models.product import ListingConcept, Product, ProductRevision
from app.models.title import TitleAsset
from app.services import image_qa_service, product_data_service, revision_qa_service, title_service
from app.services.uuid_provider import new_uuid


@dataclass
class ReadyGateResult:
    ready: bool
    blockers: list[str] = field(default_factory=list)
    selected_asset_ids: list[str] = field(default_factory=list)
    passed_count: int = 0
    required_status: dict = field(default_factory=dict)


class ReadyService:
    # ---------------- 门禁检查（只读，可重复调用） ----------------
    def evaluate(self, *, session: Session, workspace_id: str, product_id: str) -> ReadyGateResult:
        policy = image_policy()
        min_ready = int(policy["min_ready_count"])
        required_roles = list(policy["required_roles"])

        product = session.scalar(
            select(Product).where(Product.workspace_id == workspace_id, Product.id == product_id)
        )
        if product is None:
            raise ReadyGateBlockedError(detail="商品不存在")

        blockers: list[str] = []

        # 1) 永久 SKU
        if not product.internal_sku or product.state != "ACTIVE":
            blockers.append("SKU_NOT_PERMANENT")

        revision = _active_revision(session=session, workspace_id=workspace_id, product_id=product_id)
        if revision is None:
            return ReadyGateBlockedResult("NO_REVISION")

        # 2) Concept FROZEN + 标题身份
        concept = session.get(ListingConcept, revision.concept_id)
        if concept is None or concept.state != "FROZEN":
            blockers.append("CONCEPT_NOT_FROZEN")
        elif concept.title_id:
            asset = session.get(TitleAsset, concept.title_id)
            if asset is None:
                blockers.append("TITLE_IDENTITY_MISMATCH")
            elif concept.title_text != asset.title_text:
                blockers.append("TITLE_TEXT_CHANGED")

        # 最新修订级 QA 快照
        summary = revision_qa_service.latest_summary(
            session=session, workspace_id=workspace_id, revision_id=revision.id
        )
        if summary is None:
            blockers.append("REVISION_QA_MISSING")

        selected: list[str] = []
        passed = 0
        required_status: dict[str, str] = {}

        jobs = session.scalars(
            select(ImageJob)
            .where(ImageJob.workspace_id == workspace_id, ImageJob.revision_id == revision.id)
            .order_by(ImageJob.slot)
        ).all()

        for job in jobs:
            asset = _latest_asset(session=session, image_job_id=job.id)
            if asset is None:
                required_status.setdefault(job.role, "MISSING")
                if job.is_required:
                    blockers.append(f"REQUIRED_ROLE_MISSING:{job.role}")
                continue

            effective = image_qa_service.ImageQAService.effective_result(session=session, asset_id=asset.id)
            required_status[job.role] = effective

            verified = asset.integrity_state == "VERIFIED" and storage.verify(
                key=asset.storage_key,
                expected_sha256=asset.checksum_digest,
                expected_size=asset.byte_size,
            )

            if effective == "PASS" and verified:
                passed += 1
                selected.append(asset.id)
            else:
                if job.is_required:
                    blockers.append(f"REQUIRED_ROLE_NOT_PASS:{job.role}")
                if not verified:
                    blockers.append(f"BYTE_INTEGRITY_NOT_VERIFIED:slot{job.slot}")

        # 3) ProductData 存在且 QA 指纹匹配
        data = product_data_service.get(session=session, workspace_id=workspace_id, revision_id=revision.id)
        if data is None:
            blockers.append("PRODUCT_DATA_MISSING")
        elif summary is not None and data.qa_result_snapshot:
            current_fingerprint = _qa_fingerprint(summary)
            stored_fingerprint = _qa_fingerprint_from_snapshot(data.qa_result_snapshot)
            if current_fingerprint != stored_fingerprint:
                blockers.append("QA_FINGERPRINT_MISMATCH")

        # 4) 数量与必需角色
        if passed < min_ready:
            blockers.append(f"READY_COUNT_BELOW_MIN:{passed}/{min_ready}")
        for role in required_roles:
            if required_status.get(role) != "PASS":
                blockers.append(f"REQUIRED_ROLE_NOT_PASS:{role}")

        unique_blockers = sorted(set(blockers))
        return ReadyGateResult(
            ready=not unique_blockers,
            blockers=unique_blockers,
            selected_asset_ids=selected,
            passed_count=passed,
            required_status=required_status,
        )

    # ---------------- 标记 READY（原子事务） ----------------
    def mark_ready(
        self,
        *,
        session: Session,
        workspace_id: str,
        product_id: str,
        operation_key: str,
    ) -> dict:
        gate = self.evaluate(session=session, workspace_id=workspace_id, product_id=product_id)
        if not gate.ready:
            raise ReadyGateBlockedError(detail=", ".join(gate.blockers))

        revision = _active_revision(session=session, workspace_id=workspace_id, product_id=product_id)
        if revision is None:
            raise ReadyGateBlockedError(detail="无可用修订")

        # 已在事务中（由 API 层保证），此处在同一个 session 上顺序提交业原子单元
        summary = revision_qa_service.latest_summary(
            session=session, workspace_id=workspace_id, revision_id=revision.id
        )
        data = product_data_service.get(session=session, workspace_id=workspace_id, revision_id=revision.id)
        if data is not None:
            data.qa_result_snapshot = _summary_to_snapshot(summary)
            data.state = "FINAL"
            session.flush()

        usage = title_service.consume_usage(
            session=session,
            workspace_id=workspace_id,
            product_id=product_id,
            revision_id=revision.id,
            operation_key=operation_key,
        )

        ready_gate_id = new_uuid()
        revision.status = "READY_FOR_PUBLISH"
        revision.ready_gate_id = ready_gate_id
        revision.ready_at = utc_now()
        session.flush()

        record_event(
            session,
            workspace_id=workspace_id,
            entity_type="REVISION",
            entity_id=revision.id,
            event_kind=REVISION_READY,
            payload={
                "ready_gate_id": ready_gate_id,
                "selected_assets": gate.selected_asset_ids,
                "passed_count": gate.passed_count,
                "title_consumed": usage is not None,
            },
        )
        session.flush()

        return {
            "product_id": product_id,
            "revision_id": revision.id,
            "status": revision.status,
            "ready_gate_id": ready_gate_id,
            "selected_assets": gate.selected_asset_ids,
            "passed_count": gate.passed_count,
            "title_usage_created": usage is not None,
        }


def ReadyGateBlockedResult(reason: str) -> ReadyGateResult:  # noqa: N802 - 保持工厂函数语义
    return ReadyGateResult(ready=False, blockers=[reason])


def _active_revision(*, session: Session, workspace_id: str, product_id: str) -> ProductRevision | None:
    rows = session.scalars(
        select(ProductRevision)
        .where(ProductRevision.workspace_id == workspace_id, ProductRevision.product_id == product_id)
        .order_by(ProductRevision.revision_number.desc())
    ).all()
    return rows[0] if rows else None


def _latest_asset(*, session: Session, image_job_id: str) -> ImageAsset | None:
    return session.scalar(
        select(ImageAsset)
        .join(ImageAttempt, ImageAsset.attempt_id == ImageAttempt.id)
        .where(ImageAttempt.image_job_id == image_job_id)
        .order_by(ImageAsset.created_at.desc())
    )


def _qa_fingerprint(summary: RevisionQA) -> str:
    from app.core.hashing import sha256_hex

    snapshot = _summary_to_snapshot(summary)
    return sha256_hex(snapshot)


def _summary_to_snapshot(summary: RevisionQA | None) -> dict:
    if summary is None:
        return {}
    return {
        "passed": int(summary.passed_count),
        "failed": int(summary.failed_count),
        "pending": int(summary.pending_count),
        "required_role_status": summary.required_role_status or {},
    }


def _qa_fingerprint_from_snapshot(snapshot: dict) -> str:
    from app.core.hashing import sha256_hex

    return sha256_hex(
        {
            "passed": int(snapshot.get("passed", 0)),
            "failed": int(snapshot.get("failed", 0)),
            "pending": int(snapshot.get("pending", 0)),
            "required_role_status": snapshot.get("required_role_status", {}),
        }
    )
