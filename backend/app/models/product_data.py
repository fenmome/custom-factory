"""商品属性数据（每个 revision 唯一）。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HASH_TYPE, UUIDType, Base, TimestampMixin


class ProductData(Base, TimestampMixin):
    __tablename__ = "product_data"
    __table_args__ = (UniqueConstraint("revision_id", name="uk_revision_product_data"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    revision_id: Mapped[str] = mapped_column(UUIDType, nullable=False)
    product_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    concept_id: Mapped[str] = mapped_column(UUIDType, nullable=False)
    title_id: Mapped[str | None] = mapped_column(UUIDType, nullable=True)
    schema_id: Mapped[str] = mapped_column(String(128), nullable=False)
    schema_version: Mapped[str] = mapped_column(String(32), nullable=False)
    schema_hash: Mapped[str] = mapped_column(HASH_TYPE, nullable=False)
    data: Mapped[dict[str, Any]] = mapped_column(JSON, nullable=False)
    manifest_hash: Mapped[str | None] = mapped_column(HASH_TYPE, nullable=True)
    qa_result_snapshot: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", server_default="DRAFT")
