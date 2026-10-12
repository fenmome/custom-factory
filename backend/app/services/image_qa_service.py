"""图片质检：技术 QA + 语义 QA + 外观/文字规则。

铁律（agent.md 4.3）：
- QA 记录**追加式**（只 INSERT，绝不 UPDATE）
- 硬技术失败**永远不可人工放行**
- 每条记录写入 rule_id / rule_version / rule_hash / asset_checksum，实现内容寻址
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import IMAGE_QA_RECORDED, record_event, utc_now
from app.core.hashing import sha256_hex
from app.core.image_inspector import probe, sniff_is_png
from app.core.resource_loader import Resource, image_policy, load_resource
from app.core.storage import storage
from app.models.image import ImageAsset, ImageJob, ImageQA
from app.services.uuid_provider import new_uuid

TECHNICAL_RULE_PATH = "image_policy/uv_dtf_image_policy_v1_2.json"
OCR_RULE_PATH = "prompt_rules/UV_DTF_PROMPT_RULE_V1_4.json"

KIND_TECHNICAL = "TECHNICAL"
KIND_SEMANTIC = "SEMANTIC"
KIND_HUMAN = "HUMAN"
KIND_OCR = "OCR_TEXT"

RESULT_PASS = "PASS"
RESULT_FAIL = "FAIL"
RESULT_PENDING = "PENDING"

# 硬技术失败原因码 —— 人工复审**永远**不可放行
HARD_TECHNICAL_REASON_CODES = frozenset(
    {
        "MISSING_FILE",
        "CHECKSUM_MISMATCH",
        "CORRUPT_ASSET",
        "INVALID_PNG",
        "INTEGRITY_FAILURE",
        "DIMENSION_MISMATCH",
        "TRANSPARENCY",
        "UNSUPPORTED_IMAGE_FORMAT",
        "DECODE_FAILED",
    }
)

SEMANTIC_REASON_CODES = frozenset(
    {
        "PRODUCT_MISMATCH",
        "ROLE_MISMATCH",
        "CONCEPT_INCONSISTENCY",
        "TEXT_ERROR",
        "VISUAL_DEFECT",
        "REVIEW_REQUIRED_UNCERTAIN",
    }
)


def is_hard_technical(reason_code: str) -> bool:
    return reason_code in HARD_TECHNICAL_REASON_CODES


@dataclass(frozen=True)
class QAFinding:
    result: str
    reason_code: str | None
    reason_detail: str | None


class ImageQAService:
    def __init__(self, *, policy: Resource | None = None) -> None:
        self.policy = policy or image_policy()

    # ---------------- 策略读取 ----------------
    def role_requirements(self) -> dict:
        requirements = self.policy["role_qa_requirements"]
        return dict(requirements.get("common") or next(iter(requirements.values())))

    def min_ready_count(self) -> int:
        return int(self.policy["min_ready_count"])

    def planned_count(self) -> int:
        return int(self.policy["planned_count"])

    def required_roles(self) -> list[str]:
        return list(self.policy["required_roles"])

    # ---------------- 技术 QA ----------------
    def run_technical_qa(
        self,
        *,
        session: Session,
        asset: ImageAsset,
        job: ImageJob,
        operation_key: str,
        source_bytes: bytes | None = None,
    ) -> ImageQA:
        requirements = self.role_requirements()

        data = source_bytes
        if data is None:
            try:
                data = storage.read_bytes(key=asset.storage_key)
            except Exception:  # noqa: BLE001
                data = None

        if data is None:
            finding = QAFinding(RESULT_FAIL, "MISSING_FILE", "存储中找不到该资产字节")
            return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

        if not sniff_is_png(data):
            finding = QAFinding(RESULT_FAIL, "UNSUPPORTED_IMAGE_FORMAT", "仅接受 PNG，禁止格式转换")
            return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

        actual_sha = sha256_hex(data)
        if actual_sha != asset.checksum_digest:
            finding = QAFinding(RESULT_FAIL, "CHECKSUM_MISMATCH", f"声明 {asset.checksum_digest[:12]}… 实际 {actual_sha[:12]}…")
            return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

        if len(data) != asset.byte_size:
            finding = QAFinding(RESULT_FAIL, "CORRUPT_ASSET", f"声明大小 {asset.byte_size} 实际 {len(data)}")
            return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

        if asset.integrity_state != "VERIFIED":
            finding = QAFinding(RESULT_FAIL, "INTEGRITY_FAILURE", f"资产完整性状态为 {asset.integrity_state}")
            return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

        info = probe(data)
        if not info.readable or not info.is_png:
            finding = QAFinding(RESULT_FAIL, "INVALID_PNG", info.error or "PNG 解码失败")
            return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

        min_width = int(requirements["min_width"])
        min_height = int(requirements["min_height"])
        square_required = bool(requirements["square_required"])

        if info.width != asset.width or info.height != asset.height:
            finding = QAFinding(
                RESULT_FAIL, "DIMENSION_MISMATCH", f"注册 ({asset.width}x{asset.height}) 实际 ({info.width}x{info.height})"
            )
            return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

        size_ok = info.width >= min_width and info.height >= min_height
        square_ok = info.width == info.height if square_required else True
        if not (size_ok and square_ok):
            finding = QAFinding(
                RESULT_FAIL,
                "DIMENSION_MISMATCH",
                f"要求正方形且 ≥{min_width}x{min_height}，实际 {info.width}x{info.height}",
            )
            return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

        transparency_expected = bool(requirements.get("transparency_expected", False))
        if info.has_transparent_pixel and not transparency_expected:
            finding = QAFinding(RESULT_FAIL, "TRANSPARENCY", "成品图不允许透明像素")
            return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

        finding = QAFinding(RESULT_PASS, None, None)
        return self._append(session=session, asset=asset, job=job, kind=KIND_TECHNICAL, finding=finding, operation_key=operation_key, rule=self.policy)

    # ---------------- 语义 QA ----------------
    def run_semantic_qa(
        self,
        *,
        session: Session,
        asset: ImageAsset,
        job: ImageJob,
        operation_key: str,
        provider_result: str = "UNCERTAIN",
    ) -> ImageQA:
        """语义质检（PRD 8.2 / 功能说明书 2.5.2）。

        - UNCERTAIN → **FAIL（`REVIEW_REQUIRED_UNCERTAIN`）**：不确定按失败标记，
          强制进入人工复审；人工可在复审中推翻为 PASS（语义失败可推翻，
          与"硬技术失败不可放行"形成对照）。
        - PASS / FAIL 仅在提供者明确给出结论时写入。
        """
        rule = load_resource(relative_path=OCR_RULE_PATH)
        if provider_result not in {"PASS", "FAIL", "UNCERTAIN"}:
            provider_result = "UNCERTAIN"

        if provider_result == "UNCERTAIN":
            finding = QAFinding(
                RESULT_FAIL,
                "REVIEW_REQUIRED_UNCERTAIN",
                "语义判定不确定，按失败标记并强制人工复审（人工可推翻）",
            )
        elif provider_result == "PASS":
            finding = QAFinding(RESULT_PASS, None, None)
        else:
            finding = QAFinding(RESULT_FAIL, "VISUAL_DEFECT", "多模态提供者判定不通过")

        return self._append(
            session=session,
            asset=asset,
            job=job,
            kind=KIND_SEMANTIC,
            finding=finding,
            operation_key=operation_key,
            rule=rule,
        )

    # ---------------- 追加写 ----------------
    def _append(
        self,
        *,
        session: Session,
        asset: ImageAsset,
        job: ImageJob,
        kind: str,
        finding: QAFinding,
        operation_key: str,
        rule: Resource,
    ) -> ImageQA:
        record = ImageQA(
            id=new_uuid(),
            workspace_id=asset.workspace_id,
            asset_id=asset.id,
            image_job_id=job.id,
            kind=kind,
            result=finding.result,
            reason_code=finding.reason_code,
            reason_detail=finding.reason_detail,
            rule_id=str(rule.data.get("policy_id") or rule.data.get("rule_id")),
            rule_version=str(rule.data.get("version")),
            rule_hash=rule.content_hash,
            asset_checksum=asset.checksum_digest,
            operation_key=operation_key,
            overrides=None,
            evaluated_by=None,
            evaluated_at=utc_now(),
        )
        session.add(record)
        session.flush()
        record_event(
            session,
            workspace_id=asset.workspace_id,
            entity_type="IMAGE_ASSET",
            entity_id=asset.id,
            event_kind=IMAGE_QA_RECORDED,
            payload={"kind": kind, "result": finding.result, "reason_code": finding.reason_code},
        )
        return record

    # ---------------- 查询：当前有效结论 ----------------
    @staticmethod
    def latest_by_kind(*, session: Session, asset_id: str, kind: str) -> ImageQA | None:
        rows = session.scalars(
            select(ImageQA).where(ImageQA.asset_id == asset_id, ImageQA.kind == kind).order_by(ImageQA.evaluated_at.desc())
        ).all()
        return rows[0] if rows else None

    @classmethod
    def effective_result(cls, *, session: Session, asset_id: str) -> str:
        """当前有效结论（人工 > 自动）。

        - 存在硬技术 FAIL → 直接 FAIL（不可推翻）
        - 否则以最近一条 HUMAN 为准；无 HUMAN 时看 TECHNICAL + SEMANTIC 是否全 PASS
        """
        rows: Sequence[ImageQA] = session.scalars(
            select(ImageQA).where(ImageQA.asset_id == asset_id).order_by(ImageQA.evaluated_at.desc())
        ).all()
        if not rows:
            return RESULT_PENDING

        latest_technical = next((r for r in rows if r.kind == KIND_TECHNICAL), None)
        if latest_technical is not None and latest_technical.result == RESULT_FAIL:
            # 硬技术失败永远不可人工放行
            if latest_technical.reason_code and is_hard_technical(latest_technical.reason_code):
                return RESULT_FAIL

        latest_human = next((r for r in rows if r.kind == KIND_HUMAN), None)
        if latest_human is not None:
            return latest_human.result

        for kind in (KIND_TECHNICAL, KIND_SEMANTIC, KIND_OCR):
            row = next((r for r in rows if r.kind == kind), None)
            if row is not None and row.result != RESULT_PASS:
                return row.result
        return RESULT_PASS
