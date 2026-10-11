"""OCR 文字质检（FR-08.4）。

流程：图片注册后自动 OCR → 对照禁止文字规则 → 结果存为 OCR_TEXT QA，需人工确认。
无真实运行时时（`OCR_ENABLED=False`）产出 PENDING 记录，交由人工确认。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.config import settings
from app.core.events import utc_now
from app.core.exceptions import OCRRuntimeError
from app.core.resource_loader import Resource, load_resource
from app.models.image import ImageAsset, ImageJob, ImageQA
from app.providers.ocr.base import OcrResult
from app.providers.ocr.registry import get_ocr_provider
from app.services.uuid_provider import new_uuid

OCR_RULE_PATH = "prompt_rules/UV_DTF_PROMPT_RULE_V1_4.json"
KIND_OCR = "OCR_TEXT"


class OCRTextQAService:
    def __init__(self, *, rule: Resource | None = None) -> None:
        self.rule = rule or load_resource(relative_path=OCR_RULE_PATH)

    def forbidden_words(self) -> list[str]:
        return [str(w) for w in self.rule["forbidden_text"]]

    def detect(self, texts: list[str]) -> list[str]:
        """返回命中的禁止文字列表（大小写不敏感）。"""
        lowered_targets = [t.lower() for t in texts]
        hits: list[str] = []
        for word in self.forbidden_words():
            if word.lower() in lowered_targets:
                hits.append(word)
        return hits

    def evaluate(
        self,
        *,
        session: Session,
        asset: ImageAsset,
        job: ImageJob,
        operation_key: str,
        ocr_result: OcrResult | None = None,
    ) -> ImageQA:
        if ocr_result is None:
            if not settings.OCR_ENABLED:
                return self._append(
                    session=session,
                    asset=asset,
                    job=job,
                    result="PENDING",
                    reason_code="OCR_NOT_RUN",
                    reason_detail="OCR 运行时未启用，需人工确认",
                    operation_key=operation_key,
                )
            try:
                provider = get_ocr_provider()
                ocr_result = provider.extract(storage_key=asset.storage_key)
            except OCRRuntimeError:
                return self._append(
                    session=session,
                    asset=asset,
                    job=job,
                    result="PENDING",
                    reason_code="OCR_UNAVAILABLE",
                    reason_detail="OCR 运行时不可用，需人工确认",
                    operation_key=operation_key,
                )

        hits = self.detect(ocr_result.texts)
        if hits:
            return self._append(
                session=session,
                asset=asset,
                job=job,
                result="FAIL",
                reason_code="TEXT_ERROR",
                reason_detail="命中禁止文字: " + ", ".join(hits),
                operation_key=operation_key,
                regions=ocr_result.regions,
            )
        return self._append(
            session=session,
            asset=asset,
            job=job,
            result="PASS",
            reason_code=None,
            reason_detail=None,
            operation_key=operation_key,
            regions=ocr_result.regions,
        )

    def _append(
        self,
        *,
        session: Session,
        asset: ImageAsset,
        job: ImageJob,
        result: str,
        reason_code: str | None,
        reason_detail: str | None,
        operation_key: str,
        regions: list | None = None,
    ) -> ImageQA:
        record = ImageQA(
            id=new_uuid(),
            workspace_id=asset.workspace_id,
            asset_id=asset.id,
            image_job_id=job.id,
            kind=KIND_OCR,
            result=result,
            reason_code=reason_code,
            reason_detail=reason_detail,
            rule_id=str(self.rule.data.get("rule_id")),
            rule_version=str(self.rule.data.get("version")),
            rule_hash=self.rule.content_hash,
            asset_checksum=asset.checksum_digest,
            operation_key=operation_key,
            overrides={"regions": regions} if regions else None,
            evaluated_by=None,
            evaluated_at=utc_now(),
        )
        session.add(record)
        session.flush()
        return record

    @staticmethod
    def latest_for_asset(*, session: Session, asset_id: str) -> ImageQA | None:
        rows = session.scalars(
            select(ImageQA)
            .where(ImageQA.asset_id == asset_id, ImageQA.kind == KIND_OCR)
            .order_by(ImageQA.evaluated_at.desc())
        ).all()
        return rows[0] if rows else None
