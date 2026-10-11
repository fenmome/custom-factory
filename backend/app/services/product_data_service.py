"""商品属性数据构建（FR-11）。

Schema：`cf:uv-dtf-small-business-attributes:v1`（从 resources 加载，禁止硬编码）
必填字段 `surface_gate` 取值固定来自 Product Profile。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import record_event, utc_now
from app.core.hashing import sha256_hex
from app.core.resource_loader import attribute_schema, product_profile
from app.models.product import ListingConcept, Product, ProductRevision
from app.models.product_data import ProductData
from app.services.uuid_provider import new_uuid


def build_payload(*, concept: ListingConcept) -> dict[str, Any]:
    """依据 Schema 生成 data 负载。"""
    profile = product_profile()
    surface = list(concept.surface_gate or profile["surface_gate"])
    expected = list(profile["surface_gate"])
    if sorted(surface) != sorted(expected):
        surface = expected

    # Schema additionalProperties=false + required=[surface_gate]
    return {"surface_gate": surface}


def validate_against_schema(*, payload: dict[str, Any]) -> list[str]:
    """轻量 Schema 校验（避免引入 jsonschema 依赖）。返回错误列表。"""
    schema = attribute_schema()
    errors: list[str] = []

    required = schema.get("required", [])
    for key in required:
        if key not in payload:
            errors.append(f"缺少必填字段 {key}")

    properties = schema.get("properties", {})
    if schema.get("additionalProperties") is False:
        for key in payload:
            if key not in properties:
                errors.append(f"不允许的字段 {key}")

    surface_spec = properties.get("surface_gate", {})
    const = surface_spec.get("const")
    if const is not None and "surface_gate" in payload:
        if sorted(payload["surface_gate"]) != sorted(const):
            errors.append("surface_gate 取值不符合常量约束")
    return errors


def build_or_refresh(
    *,
    session: Session,
    workspace_id: str,
    revision: ProductRevision,
    qa_snapshot: dict | None = None,
) -> ProductData:
    concept = session.get(ListingConcept, revision.concept_id)
    if concept is None:
        raise ValueError(f"revision {revision.id} 无 Concept")

    payload = build_payload(concept=concept)
    errors = validate_against_schema(payload=payload)
    if errors:
        raise ValueError("; ".join(errors))

    schema = attribute_schema()
    product = session.get(Product, revision.product_id)

    existing = session.scalar(
        select(ProductData).where(
            ProductData.workspace_id == workspace_id, ProductData.revision_id == revision.id
        )
    )

    manifest = {
        "internal_sku": product.internal_sku if product else None,
        "title_text": concept.title_text,
        "brand_name": concept.brand_name,
        "object": concept.object,
        "core_hash": concept.core_hash,
        "data": payload,
    }

    if existing is not None:
        existing.data = payload
        existing.manifest_hash = sha256_hex(manifest)
        existing.qa_result_snapshot = qa_snapshot
        existing.concept_id = concept.id
        existing.title_id = concept.title_id
        session.flush()
        return existing

    record = ProductData(
        id=new_uuid(),
        workspace_id=workspace_id,
        revision_id=revision.id,
        product_id=revision.product_id,
        concept_id=concept.id,
        title_id=concept.title_id,
        schema_id=str(schema["schema_id"]),
        schema_version=str(schema["version"]),
        schema_hash=schema.content_hash,
        data=payload,
        manifest_hash=sha256_hex(manifest),
        qa_result_snapshot=qa_snapshot,
        state="DRAFT",
    )
    session.add(record)
    session.flush()

    record_event(
        session,
        workspace_id=workspace_id,
        entity_type="REVISION",
        entity_id=revision.id,
        event_kind="PRODUCT_DATA_BUILT",
        payload={"schema_id": record.schema_id, "hash": record.schema_hash},
    )
    return record


def get(*, session: Session, workspace_id: str, revision_id: str) -> ProductData | None:
    return session.scalar(
        select(ProductData).where(
            ProductData.workspace_id == workspace_id, ProductData.revision_id == revision_id
        )
    )


def mark_final(*, session: Session, record: ProductData) -> ProductData:
    record.state = "FINAL"
    record.updated_at = utc_now()
    session.flush()
    return record
