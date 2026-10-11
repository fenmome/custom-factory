"""批次创建与 SKU 原子分配（FR-01 / FR-02）。

关键约束：创建 N 个 SKU 必须在**同一数据库事务**内完成，
任何一个失败整体回滚，绝不产生半成品批次。
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.events import BATCH_CREATED, SKU_ALLOCATED, record_event
from app.core.exceptions import ValidationError
from app.core.hashing import canonical_json_bytes, sha256_hex
from app.core.resource_loader import title_source
from app.models.product import Batch, ListingConcept, Product, ProductRevision
from app.models.sku import ProductTypeSkuConfig
from app.services import sku_service
from app.services.uuid_provider import new_uuid


@dataclass(frozen=True)
class CreateBatchCommand:
    """不可变命令对象，含幂等键。"""

    workspace_id: str
    product_type_code: str
    usage_code: str
    quantity: int
    image_generation_route: str
    style_code: str | None
    palette_code: str | None
    request_key: str
    operation_key: str
    created_by_user_id: str

    def snapshot(self) -> dict:
        """规范请求快照。"""
        return {
            "workspace_id": self.workspace_id,
            "product_type_code": self.product_type_code,
            "usage_code": self.usage_code,
            "quantity": self.quantity,
            "image_generation_route": self.image_generation_route,
            "style_code": self.style_code,
            "palette_code": self.palette_code,
            "request_key": self.request_key,
        }

    def snapshot_hash(self) -> str:
        return sha256_hex(canonical_json_bytes(self.snapshot()))


def _require_positive_quantity(quantity: int) -> None:
    if quantity <= 0:
        raise ValidationError(detail="生产数量必须 ≥ 1")


def _require_supported_route(route: str) -> None:
    if route not in {"API", "CODEX"}:
        raise ValidationError(detail="image_generation_route 仅支持 API / CODEX")


def _require_usage(usage_code: str) -> None:
    pin_usage = title_source()["source_pin"]["usage_code"]
    if usage_code != pin_usage:
        raise ValidationError(detail=f"当前仅支持使用场景 {pin_usage}")


def create_batch(*, session: Session, command: CreateBatchCommand) -> Batch:
    """在同一事务内创建批次 + N 个 Product / Revision / Concept，并原子分配 SKU。"""
    _require_positive_quantity(command.quantity)
    _require_supported_route(command.image_generation_route)
    _require_usage(command.usage_code)

    config = sku_service.get_config(
        session=session, workspace_id=command.workspace_id, product_type_code=command.product_type_code
    )
    sku_service.ensure_usable(config=config)

    snapshot_hash = command.snapshot_hash()

    existing = session.scalar(
        select(Batch).where(
            Batch.workspace_id == command.workspace_id,
            Batch.request_key == command.request_key,
        )
    )
    if existing is not None:
        if existing.input_snapshot_hash != snapshot_hash:
            raise ValidationError(detail="同一 request_key 携带了不同的请求内容")
        return existing

    batch = Batch(
        id=new_uuid(),
        workspace_id=command.workspace_id,
        product_type_id=config.id,
        requested_quantity=command.quantity,
        image_generation_route=command.image_generation_route,
        control_state="ACTIVE",
        request_key=command.request_key,
        input_snapshot_hash=snapshot_hash,
        usage_code=command.usage_code,
        style_code=command.style_code,
        palette_code=command.palette_code,
        created_by_user_id=command.created_by_user_id,
    )
    session.add(batch)
    session.flush()

    allocations = sku_service.allocate_sequence_block(
        session=session, config=config, quantity=command.quantity
    )

    for sku, sequence, prefix in allocations:
        product = Product(
            id=new_uuid(),
            workspace_id=command.workspace_id,
            batch_id=batch.id,
            sku_namespace=config.id,
            internal_sku=sku,
            allocated_prefix=prefix,
            allocated_sequence=sequence,
            state="ACTIVE",
        )
        session.add(product)
        session.flush()

        revision = ProductRevision(
            id=new_uuid(),
            workspace_id=command.workspace_id,
            product_id=product.id,
            batch_id=batch.id,
            revision_number=1,
            status="DRAFT",
        )
        session.add(revision)
        session.flush()

        concept = ListingConcept(
            id=new_uuid(),
            workspace_id=command.workspace_id,
            revision_id=revision.id,
            usage_code=command.usage_code,
            state="DRAFT",
        )
        session.add(concept)
        session.flush()

        revision.concept_id = concept.id
        session.flush()

        record_event(
            session,
            workspace_id=command.workspace_id,
            entity_type="PRODUCT",
            entity_id=product.id,
            event_kind=SKU_ALLOCATED,
            payload={"internal_sku": sku, "prefix": prefix, "sequence": sequence, "batch_id": batch.id},
        )

    record_event(
        session,
        workspace_id=command.workspace_id,
        entity_type="BATCH",
        entity_id=batch.id,
        event_kind=BATCH_CREATED,
        payload={"quantity": command.quantity, "snapshot_hash": snapshot_hash},
    )
    session.flush()
    return batch


def get_batch(*, session: Session, workspace_id: str, batch_id: str) -> Batch | None:
    return session.scalar(
        select(Batch).where(Batch.workspace_id == workspace_id, Batch.id == batch_id)
    )


def list_batches(*, session: Session, workspace_id: str, limit: int = 20, offset: int = 0) -> Sequence[Batch]:
    return session.scalars(
        select(Batch)
        .where(Batch.workspace_id == workspace_id)
        .order_by(Batch.created_at.desc())
        .limit(limit)
        .offset(offset)
    ).all()


def count_batches(*, session: Session, workspace_id: str) -> int:
    return int(
        session.scalar(select(func.count()).select_from(Batch).where(Batch.workspace_id == workspace_id)) or 0
    )


def list_revisions(
    *, session: Session, workspace_id: str, batch_id: str, limit: int = 500
) -> Sequence[ProductRevision]:
    return session.scalars(
        select(ProductRevision)
        .where(ProductRevision.workspace_id == workspace_id, ProductRevision.batch_id == batch_id)
        .order_by(ProductRevision.created_at)
        .limit(limit)
    ).all()


def resolve_product_type_map(
    *, session: Session, workspace_id: str
) -> dict[str, ProductTypeSkuConfig]:
    rows = session.scalars(
        select(ProductTypeSkuConfig).where(ProductTypeSkuConfig.workspace_id == workspace_id)
    ).all()
    return {row.id: row for row in rows}
