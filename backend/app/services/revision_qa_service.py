"""修订级 QA 汇总（READY 判定的输入之一）。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import utc_now
from app.core.resource_loader import image_policy
from app.models.image import ImageJob, ImageQA, RevisionQA
from app.services import image_qa_service
from app.services.uuid_provider import new_uuid

KIND_MAPPING = {
    "TECHNICAL": image_qa_service.KIND_TECHNICAL,
    "SEMANTIC": image_qa_service.KIND_SEMANTIC,
    "HUMAN": image_qa_service.KIND_HUMAN,
    "OCR_TEXT": image_qa_service.KIND_OCR,
}


class RevisionQAService:
    def summarise(
        self,
        *,
        session: Session,
        workspace_id: str,
        revision_id: str,
    ) -> RevisionQA:
        policy = image_policy()
        required_roles = list(policy["required_roles"])

        jobs = session.scalars(
            select(ImageJob).where(ImageJob.workspace_id == workspace_id, ImageJob.revision_id == revision_id)
        ).all()

        passed = failed = pending = 0
        role_status: dict[str, dict] = {}
        snapshot: list[dict] = []

        for job in jobs:
            asset = _latest_asset(session=session, image_job_id=job.id)
            if asset is None:
                pending += 1
                role_status[job.role] = {"state": "PENDING", "has_asset": False, "is_required": job.is_required}
                continue

            result = image_qa_service.ImageQAService.effective_result(session=session, asset_id=asset.id)
            role_status[job.role] = {
                "state": result,
                "slot": job.slot,
                "asset_id": asset.id,
                "is_required": job.is_required,
            }
            snapshot.append(
                {
                    "slot": job.slot,
                    "role": job.role,
                    "asset_id": asset.id,
                    "checksum": asset.checksum_digest,
                    "result": result,
                }
            )

            if result == "PASS":
                passed += 1
            elif result == "FAIL":
                failed += 1
            else:
                pending += 1

        required_ok = all(
            role_status.get(role, {}).get("state") == "PASS" for role in required_roles
        )
        min_ready = int(policy["min_ready_count"])
        if failed > 0:
            # 存在任一 FAIL → 修订级失败（不含人工尚未裁定的 PENDING）
            overall = "FAIL"
        elif required_ok and passed >= min_ready:
            # 必需角色全部通过且达到最少 5 张 → PASS（未上传槽位允许留空）
            overall = "PASS"
        else:
            # 尚未收齐图片或语义待人工裁定
            overall = "PENDING"

        record = RevisionQA(
            id=new_uuid(),
            workspace_id=workspace_id,
            revision_id=revision_id,
            result=overall,
            passed_count=passed,
            failed_count=failed,
            pending_count=pending,
            required_role_status=role_status,
            qa_result_snapshot={"assets": snapshot},
            evaluated_at=utc_now(),
        )
        session.add(record)
        session.flush()

        # FR-09：QA 汇总后在同一事务内触发生产保护评估（YELLOW 告警 / RED 按最小范围暂停）
        _evaluate_guard(session=session, workspace_id=workspace_id, revision_id=revision_id)
        return record


def _evaluate_guard(*, session: Session, workspace_id: str, revision_id: str) -> None:
    from app.models.product import Batch, ProductRevision
    from app.services import production_guard_service

    product_type_id = None
    revision = session.get(ProductRevision, revision_id)
    if revision is not None:
        batch = session.get(Batch, revision.batch_id)
        product_type_id = batch.product_type_id if batch is not None else None

    production_guard_service.ProductionGuardService().evaluate_and_apply(
        session=session, workspace_id=workspace_id, product_type_id=product_type_id
    )


def _latest_asset(*, session: Session, image_job_id: str):
    from app.models.image import ImageAsset, ImageAttempt

    asset = session.scalar(
        select(ImageAsset)
        .join(ImageAttempt, ImageAsset.attempt_id == ImageAttempt.id)
        .where(ImageAttempt.image_job_id == image_job_id)
        .order_by(ImageAsset.created_at.desc())
    )
    return asset


def latest_summary(*, session: Session, workspace_id: str, revision_id: str) -> RevisionQA | None:
    rows = session.scalars(
        select(RevisionQA)
        .where(RevisionQA.workspace_id == workspace_id, RevisionQA.revision_id == revision_id)
        .order_by(RevisionQA.evaluated_at.desc())
    ).all()
    return rows[0] if rows else None
