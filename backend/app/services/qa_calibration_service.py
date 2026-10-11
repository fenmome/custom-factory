"""QA 校准（FR-08 校准机制）。

- 每个产品类型的前 3 个批次为校准期，自动失败的 SKU 必须人工复审
- 每批次稳定采样最多 20 个自动通过的 SKU 集合
- 统计 TRUE_PASS / FALSE_PASS / TRUE_FAIL / FALSE_FAIL
- ≥3 批次 + ≥100 张人工复审图片 → 触发 `QA_RULE_REVIEW_DUE`
"""

from __future__ import annotations

import random
from dataclasses import dataclass
from datetime import timedelta

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models.image import ImageAsset, ImageAttempt, ImageJob, ImageQA
from app.models.product import Batch, Product, ProductRevision

CALIBRATION_BATCH_LIMIT = 3
SAMPLE_SIZE = 20
REVIEW_DUE_MIN_BATCHES = 3
REVIEW_DUE_MIN_IMAGES = 100


@dataclass(frozen=True)
class CalibrationReport:
    product_type_id: str
    batch_count: int
    human_reviewed_images: int
    agreement_rate: float
    false_pass: int
    false_fail: int
    true_pass: int
    true_fail: int
    by_role: list[dict]
    by_reason: list[dict]
    review_due: bool


class QACalibrationService:
    def list_calibration_batches(
        self, *, session: Session, workspace_id: str, product_type_id: str
    ) -> list[Batch]:
        """校准期批次：该产品类型最早的前 3 个批次。"""
        return list(
            session.scalars(
                select(Batch)
                .where(Batch.workspace_id == workspace_id, Batch.product_type_id == product_type_id)
                .order_by(Batch.created_at)
                .limit(CALIBRATION_BATCH_LIMIT)
            ).all()
        )

    def sample_auto_pass_products(
        self,
        *,
        session: Session,
        workspace_id: str,
        batch_id: str,
        sample_size: int = SAMPLE_SIZE,
        seed: int | None = None,
    ) -> list[str]:
        """每批次稳定采样（同一 seed 结果一致）。"""
        product_ids = self._auto_pass_product_ids(session=session, workspace_id=workspace_id, batch_id=batch_id)
        if not seed:
            seed = _stable_seed(batch_id)
        rng = random.Random(seed)  # noqa: S311 - 采样非密码学用途
        rng.shuffle(product_ids)
        return product_ids[:sample_size]

    @staticmethod
    def _auto_pass_product_ids(*, session: Session, workspace_id: str, batch_id: str) -> list[str]:
        rows = session.scalars(
            select(Product.id)
            .join(ProductRevision, ProductRevision.product_id == Product.id)
            .where(Product.workspace_id == workspace_id, ProductRevision.batch_id == batch_id)
        ).all()
        result: list[str] = []
        for product_id in rows:
            flags = _judged_assets(session=session, workspace_id=workspace_id, product_id=product_id)
            if not flags:
                continue
            if all(flags):
                result.append(product_id)
        return result

    def build_report(
        self, *, session: Session, workspace_id: str, product_type_id: str
    ) -> CalibrationReport:
        batches = self.list_calibration_batches(
            session=session, workspace_id=workspace_id, product_type_id=product_type_id
        )
        batch_ids = [b.id for b in batches]

        human_rows = list(
            session.scalars(
                select(ImageQA)
                .join(ImageJob, ImageQA.image_job_id == ImageJob.id)
                .join(ProductRevision, ImageJob.revision_id == ProductRevision.id)
                .where(
                    ImageQA.workspace_id == workspace_id,
                    ImageQA.kind == "HUMAN",
                )
            ).all()
        )
        if batch_ids:
            human_rows = [r for r in human_rows if _revision_batch(session, r.image_job_id) in batch_ids]

        total = len(human_rows)
        true_pass = false_pass = true_fail = false_fail = 0
        by_role_counter: dict[str, dict[str, int]] = {}
        by_reason_counter: dict[str, dict[str, int]] = {}

        for row in human_rows:
            auto = _latest_auto_result(session=session, asset_id=row.asset_id)
            job = session.get(ImageJob, row.image_job_id)
            role = job.role if job else "UNKNOWN"
            bucket = by_role_counter.setdefault(role, {"agree": 0, "disagree": 0})
            reason = row.reason_code or "NONE"
            reason_bucket = by_reason_counter.setdefault(reason, {"agree": 0, "disagree": 0})

            agreed = (row.result == auto)
            if agreed:
                bucket["agree"] += 1
                reason_bucket["agree"] += 1
                if row.result == "PASS":
                    true_pass += 1
                else:
                    true_fail += 1
            else:
                bucket["disagree"] += 1
                reason_bucket["disagree"] += 1
                if row.result == "PASS":
                    false_pass += 1  # 漏检：机器 FAIL，人工 PASS
                else:
                    false_fail += 1  # 误杀：机器 PASS，人工 FAIL

        agreement = (true_pass + true_fail) / total if total else 0.0

        return CalibrationReport(
            product_type_id=product_type_id,
            batch_count=len(batches),
            human_reviewed_images=total,
            agreement_rate=round(agreement * 100, 2),
            false_pass=false_pass,
            false_fail=false_fail,
            true_pass=true_pass,
            true_fail=true_fail,
            by_role=[
                {"role": role, "agree": v["agree"], "disagree": v["disagree"]}
                for role, v in sorted(by_role_counter.items())
            ],
            by_reason=[
                {"reason_code": reason, "agree": v["agree"], "disagree": v["disagree"]}
                for reason, v in sorted(by_reason_counter.items())
            ],
            review_due=len(batches) >= REVIEW_DUE_MIN_BATCHES and total >= REVIEW_DUE_MIN_IMAGES,
        )

    def due_reports(self, *, session: Session, workspace_id: str) -> list[CalibrationReport]:
        product_type_ids = [
            row[0]
            for row in session.execute(
                select(Batch.product_type_id)
                .where(Batch.workspace_id == workspace_id)
                .group_by(Batch.product_type_id)
            ).all()
        ]
        reports = [self.build_report(session=session, workspace_id=workspace_id, product_type_id=pt) for pt in product_type_ids]
        return [r for r in reports if r.review_due]

    def count_stale_claims(self, *, session: Session, workspace_id: str, minutes: int = 30) -> int:
        from app.models.guard import SkuGenerationClaim

        from app.core.events import utc_now

        threshold = utc_now() - timedelta(minutes=minutes)
        return int(
            session.scalar(
                select(func.count())
                .select_from(SkuGenerationClaim)
                .where(
                    SkuGenerationClaim.workspace_id == workspace_id,
                    SkuGenerationClaim.state == "ACTIVE",
                    SkuGenerationClaim.last_activity_at < threshold,
                )
            )
            or 0
        )


def _stable_seed(batch_id: str) -> int:
    return sum(bytearray(batch_id.encode("utf-8")))


def _revision_batch(session: Session, image_job_id: str) -> str | None:
    job = session.get(ImageJob, image_job_id)
    if job is None:
        return None
    revision = session.get(ProductRevision, job.revision_id)
    return revision.batch_id if revision else None


def _latest_auto_result(*, session: Session, asset_id: str) -> str | None:
    row = session.scalar(
        select(ImageQA)
        .where(ImageQA.asset_id == asset_id, ImageQA.kind.in_(["TECHNICAL", "SEMANTIC"]))
        .order_by(ImageQA.evaluated_at.desc())
    )
    return row.result if row else None


def _judged_assets(*, session: Session, workspace_id: str, product_id: str) -> list[bool]:
    revision = session.scalar(
        select(ProductRevision)
        .where(ProductRevision.workspace_id == workspace_id, ProductRevision.product_id == product_id)
        .order_by(ProductRevision.revision_number.desc())
    )
    if revision is None:
        return []
    rows = session.scalars(
        select(ImageJob.id).where(ImageJob.revision_id == revision.id)
    ).all()
    flags: list[bool] = []
    for job_id in rows:
        asset = session.scalar(
            select(ImageAsset)
            .join(ImageAttempt, ImageAsset.attempt_id == ImageAttempt.id)
            .where(ImageAttempt.image_job_id == job_id)
            .order_by(ImageAsset.created_at.desc())
        )
        if asset is None:
            continue
        result = _latest_auto_result(session=session, asset_id=asset.id)
        flags.append(result == "PASS")
    return flags
