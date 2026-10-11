"""标题资产 / 预留 / 使用记录。"""

from __future__ import annotations

from sqlalchemy import DateTime, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HASH_TYPE, UUIDType, Base, TimestampMixin


class TitleAsset(Base, TimestampMixin):
    """离线预生成的已审批标题池（全局资源，不属于任何 workspace）。"""

    __tablename__ = "title_assets"

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    title_text: Mapped[str] = mapped_column(Text, nullable=False)
    editorial_status: Mapped[str] = mapped_column(
        String(32), nullable=False, default="DRAFT", server_default="DRAFT"
    )
    pool_version: Mapped[str] = mapped_column(String(32), nullable=False)
    source_sha: Mapped[str] = mapped_column(HASH_TYPE, nullable=False)
    source_manifest_id: Mapped[str] = mapped_column(String(255), nullable=True)
    approval_overlay_id: Mapped[str | None] = mapped_column(String(255), nullable=True)
    approval_overlay_hash: Mapped[str | None] = mapped_column(HASH_TYPE, nullable=True)
    query_id: Mapped[str | None] = mapped_column(String(128), nullable=True)


class TitleReservation(Base, TimestampMixin):
    """AVAILABLE → RESERVED → USED / RELEASED，每个 product 唯一。"""

    __tablename__ = "title_reservations"
    __table_args__ = (UniqueConstraint("product_id", name="uk_product_reservation"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(UUIDType, nullable=False)
    revision_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    title_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="RESERVED", server_default="RESERVED")
    reserved_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    used_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    released_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class TitleUsage(Base, TimestampMixin):
    """标题消耗记录：首次 READY 成功写入 1 条，后续修订不再消耗。"""

    __tablename__ = "title_usages"

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    revision_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    title_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    title_text: Mapped[str] = mapped_column(Text, nullable=False)
    operation_key: Mapped[str] = mapped_column(String(128), nullable=False, unique=True)
    used_at: Mapped[DateTime] = mapped_column(DateTime(timezone=True), nullable=False)
