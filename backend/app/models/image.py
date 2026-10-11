"""图片任务 / 尝试 / 资产 / QA / 修订级 QA。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HASH_TYPE, UUIDType, Base, TimestampMixin


class ImageJob(Base, TimestampMixin):
    """8 槽位中的一个图片任务。

    状态：PENDING → PLANNED → CLAIMED → CALLING → ASSET_RECORDED → SETTLED
    """

    __tablename__ = "image_jobs"
    __table_args__ = (UniqueConstraint("revision_id", "slot", name="uk_rev_slot"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    revision_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    slot: Mapped[int] = mapped_column(Integer, nullable=False)
    role: Mapped[str] = mapped_column(String(64), nullable=False)
    display_order: Mapped[int] = mapped_column(Integer, nullable=False)
    is_required: Mapped[bool] = mapped_column(Boolean, nullable=False, default=False, server_default="0")
    state: Mapped[str] = mapped_column(
        String(24), nullable=False, default="PENDING", server_default="PENDING"
    )
    control_generation: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    prompt_source_hash: Mapped[str | None] = mapped_column(HASH_TYPE, nullable=True)
    rendered_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)


class ImageAttempt(Base, TimestampMixin):
    __tablename__ = "image_attempts"

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    image_job_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    attempt_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="PENDING", server_default="PENDING")
    provider: Mapped[str | None] = mapped_column(String(64), nullable=True)
    model: Mapped[str | None] = mapped_column(String(128), nullable=True)
    prompt_source_git_revision: Mapped[str | None] = mapped_column(String(255), nullable=True)
    prompt_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prompt_source_hash: Mapped[str | None] = mapped_column(HASH_TYPE, nullable=True)
    rendered_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    settled_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ImageAsset(Base, TimestampMixin):
    __tablename__ = "image_assets"
    __table_args__ = (UniqueConstraint("attempt_id", name="uk_attempt"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    attempt_id: Mapped[str] = mapped_column(UUIDType, nullable=False)
    image_job_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    provenance_kind: Mapped[str] = mapped_column(
        String(16), nullable=False, default="GENERATED", server_default="GENERATED"
    )
    integrity_state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="UNVERIFIED", server_default="UNVERIFIED"
    )
    storage_profile: Mapped[str] = mapped_column(String(64), nullable=False)
    storage_key: Mapped[str] = mapped_column(String(512), nullable=False)
    checksum_algorithm: Mapped[str] = mapped_column(
        String(16), nullable=False, default="sha256", server_default="sha256"
    )
    checksum_digest: Mapped[str] = mapped_column(HASH_TYPE, nullable=False)
    byte_size: Mapped[int] = mapped_column(BigInteger, nullable=False)
    width: Mapped[int] = mapped_column(Integer, nullable=False)
    height: Mapped[int] = mapped_column(Integer, nullable=False)
    mime_type: Mapped[str] = mapped_column(
        String(32), nullable=False, default="image/png", server_default="image/png"
    )


class ImageQA(Base, TimestampMixin):
    """追加式 QA 记录：只能 INSERT，禁止 UPDATE（见 services/image_qa_service.py）。"""

    __tablename__ = "image_qa"
    __table_args__ = (UniqueConstraint("asset_id", "rule_hash", "kind", "operation_key", name="uk_asset_rule"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    asset_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    image_job_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    kind: Mapped[str] = mapped_column(String(16), nullable=False)
    result: Mapped[str] = mapped_column(String(8), nullable=False)
    reason_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    reason_detail: Mapped[str | None] = mapped_column(Text, nullable=True)
    rule_id: Mapped[str] = mapped_column(String(128), nullable=False)
    rule_version: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_hash: Mapped[str] = mapped_column(HASH_TYPE, nullable=False)
    asset_checksum: Mapped[str] = mapped_column(HASH_TYPE, nullable=False)
    operation_key: Mapped[str] = mapped_column(String(128), nullable=False)
    overrides: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evaluated_by: Mapped[str | None] = mapped_column(UUIDType, nullable=True)
    evaluated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)


class RevisionQA(Base, TimestampMixin):
    """修订级 QA 汇总快照，READY 判定的输入之一。"""

    __tablename__ = "revision_qa"

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    revision_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    result: Mapped[str] = mapped_column(String(8), nullable=False, default="PENDING", server_default="PENDING")
    passed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    failed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    pending_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    required_role_status: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    qa_result_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    evaluated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
