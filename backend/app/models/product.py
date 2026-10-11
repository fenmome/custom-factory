"""批次 / 商品 / 修订 / 冻结概念。"""

from __future__ import annotations

from typing import Any

from sqlalchemy import JSON, Boolean, DateTime, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import HASH_TYPE, UUIDType, Base, TimestampMixin


class Batch(Base, TimestampMixin):
    __tablename__ = "batches"
    __table_args__ = (UniqueConstraint("workspace_id", "request_key", name="uk_request"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    product_type_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    requested_quantity: Mapped[int] = mapped_column(Integer, nullable=False)
    image_generation_route: Mapped[str] = mapped_column(
        String(16), nullable=False, default="CODEX", server_default="CODEX"
    )
    control_state: Mapped[str] = mapped_column(String(32), nullable=False, default="ACTIVE", server_default="ACTIVE")
    request_key: Mapped[str] = mapped_column(String(128), nullable=False)
    input_snapshot_hash: Mapped[str] = mapped_column(HASH_TYPE, nullable=False)
    usage_code: Mapped[str] = mapped_column(String(64), nullable=False)
    style_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    palette_code: Mapped[str | None] = mapped_column(String(32), nullable=True)
    prepared_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    created_by_user_id: Mapped[str] = mapped_column(UUIDType, nullable=False)


class Product(Base, TimestampMixin):
    __tablename__ = "products"
    __table_args__ = (UniqueConstraint("internal_sku", name="uk_sku"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    sku_namespace: Mapped[str] = mapped_column(UUIDType, nullable=False)
    internal_sku: Mapped[str] = mapped_column(String(64), nullable=False)
    allocated_prefix: Mapped[str] = mapped_column(String(32), nullable=False)
    allocated_sequence: Mapped[int] = mapped_column(Integer, nullable=False)
    state: Mapped[str] = mapped_column(
        String(16), nullable=False, default="ACTIVE", server_default="ACTIVE"
    )


class ProductRevision(Base, TimestampMixin):
    """修订：DRAFT → FROZEN → READY_FOR_PUBLISH"""

    __tablename__ = "product_revisions"
    __table_args__ = (UniqueConstraint("product_id", "revision_number", name="uk_product_rev"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    product_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    batch_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    revision_number: Mapped[int] = mapped_column(Integer, nullable=False, default=1, server_default="1")
    concept_id: Mapped[str | None] = mapped_column(UUIDType, nullable=True)
    status: Mapped[str] = mapped_column(
        String(24), nullable=False, default="DRAFT", server_default="DRAFT"
    )
    image_policy_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    image_policy_version: Mapped[str | None] = mapped_column(String(32), nullable=True)
    image_policy_content_hash: Mapped[str | None] = mapped_column(HASH_TYPE, nullable=True)
    ready_gate_id: Mapped[str | None] = mapped_column(UUIDType, nullable=True)
    ready_at: Mapped[DateTime | None] = mapped_column(DateTime(timezone=True), nullable=True)


class ListingConcept(Base, TimestampMixin):
    """冻结的商品概念。一旦 FROZEN 不可变更，只能新建修订。"""

    __tablename__ = "listing_concepts"

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    revision_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    title_id: Mapped[str | None] = mapped_column(UUIDType, nullable=True)
    title_text: Mapped[str | None] = mapped_column(Text, nullable=True)
    state: Mapped[str] = mapped_column(String(16), nullable=False, default="DRAFT", server_default="DRAFT")
    usage_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    object: Mapped[str | None] = mapped_column(String(64), nullable=True)
    use_case: Mapped[str | None] = mapped_column(String(64), nullable=True)
    purpose: Mapped[str | None] = mapped_column(Text, nullable=True)
    product_profile_id: Mapped[str | None] = mapped_column(String(64), nullable=True)
    semantic_payload_hash: Mapped[str | None] = mapped_column(HASH_TYPE, nullable=True)
    surface_gate: Mapped[list[str] | None] = mapped_column(JSON, nullable=True)
    brand_name: Mapped[str | None] = mapped_column(String(128), nullable=True)
    visual_plan: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    customization_constraints: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    fulfillment_constraints: Mapped[dict[str, Any] | None] = mapped_column(JSON, nullable=True)
    core_hash: Mapped[str | None] = mapped_column(HASH_TYPE, nullable=True, index=True)


_ = Boolean
