"""生产暂停控制 / SKU 领取协调。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDType, Base


class ProductionPauseControl(Base):
    """生产保护暂停控制。

    PAUSED → TRIAL_RUNNING → RESOLVED（任一失败回退 PAUSED）
    """

    __tablename__ = "production_pause_controls"

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    scope_kind: Mapped[str] = mapped_column(String(32), nullable=False)
    target: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="PAUSED", server_default="PAUSED")
    trigger_rule_id: Mapped[str] = mapped_column(String(32), nullable=False)
    rule_text: Mapped[str] = mapped_column(Text, nullable=False)
    reason: Mapped[str] = mapped_column(Text, nullable=False)
    paused_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    updated_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    trial_sku_limit: Mapped[int] = mapped_column(Integer, nullable=False, default=3, server_default="3")
    trial_claim_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    trial_completed_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    trial_pass_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    trial_fail_count: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    resolved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class SkuGenerationClaim(Base):
    """SKU 领取协调（同一 SKU 由单一执行器 / 单一会话完成）。"""

    __tablename__ = "sku_generation_claims"
    __table_args__ = (UniqueConstraint("revision_id", "executor_kind", "executor_id", name="uk_rev_executor"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    revision_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    executor_kind: Mapped[str] = mapped_column(String(8), nullable=False)
    executor_id: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="ACTIVE", server_default="ACTIVE")
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    last_activity_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
