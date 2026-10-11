"""审计事件与幂等记录。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, BigInteger, DateTime, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.core.time_utils import utc_now
from app.models.base import UUIDType, Base
from app.services.uuid_provider import new_uuid

# SQLite 仅对 `INTEGER PRIMARY KEY` 自增，故做方言变体；MySQL 仍使用 BIGINT
_AUTO_ID = BigInteger().with_variant(Integer, "sqlite")


class LifecycleEvent(Base):
    """追加式审计流水（自增主键）。"""

    __tablename__ = "lifecycle_events"

    id: Mapped[int] = mapped_column(_AUTO_ID, primary_key=True, autoincrement=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    entity_type: Mapped[str] = mapped_column(String(64), nullable=False)
    entity_id: Mapped[str] = mapped_column(UUIDType, nullable=False)
    event_kind: Mapped[str] = mapped_column(String(64), nullable=False)
    payload: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    occurred_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, index=True)


class IdempotencyRecord(Base):
    """幂等键去重表。"""

    __tablename__ = "idempotency_records"
    __table_args__ = (UniqueConstraint("workspace_id", "operation_key", "scope", name="uk_ws_opkey_scope"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True, default=new_uuid)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    operation_key: Mapped[str] = mapped_column(String(128), nullable=False)
    scope: Mapped[str] = mapped_column(String(64), nullable=False)
    request_fingerprint: Mapped[str] = mapped_column(String(64), nullable=False)
    response_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    created_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False, default=utc_now)
