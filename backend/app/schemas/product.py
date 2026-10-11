"""商品 / 产品类型 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import OperationKeyMixin


class ProductTypeUpsert(BaseModel):
    product_type_code: str = Field(..., min_length=1, max_length=64)
    display_name: str = Field(..., min_length=1, max_length=255)
    prefix: str = Field(..., min_length=1, max_length=32)
    sequence_width: int = Field(default=6, ge=1, le=12)
    is_enabled: bool = True


class ProductTypeResponse(BaseModel):
    id: str
    product_type_code: str
    display_name: str
    prefix: str
    sequence_width: int
    last_sequence: int
    is_enabled: bool
    created_at: datetime


class ImageBrief(BaseModel):
    slot: int
    role: str
    is_required: bool
    job_state: str
    asset_id: str | None = None
    width: int | None = None
    height: int | None = None
    integrity_state: str | None = None
    effective_result: str | None = None
    technical: dict | None = None
    semantic: dict | None = None
    human: dict | None = None
    ocr: dict | None = None


class ReadyGateView(BaseModel):
    ready: bool
    blockers: list[str]
    passed_count: int
    required_status: dict


class SkuDetail(BaseModel):
    product_id: str
    internal_sku: str
    batch_id: str
    revision_id: str
    revision_status: str
    title_text: str | None = None
    brand_name: str | None = None
    object: str | None = None
    core_hash: str | None = None
    images: list[ImageBrief]
    ready_gate: ReadyGateView
    created_at: datetime | None = None


class ReadyRequest(OperationKeyMixin):
    pass


class ReadyResponse(BaseModel):
    product_id: str
    revision_id: str
    status: str
    ready_gate_id: str
    selected_assets: list[str]
    passed_count: int
    title_usage_created: bool
