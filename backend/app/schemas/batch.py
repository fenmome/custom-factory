"""批次 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, Field

from app.schemas.common import OperationKeyMixin


class BatchCreateRequest(OperationKeyMixin):
    request_key: str = Field(..., min_length=8, max_length=128, description="业务请求去重键")
    product_type_code: str = Field(default="UV_DTF", min_length=1, max_length=64)
    usage_code: str = Field(default="small_business_packaging", min_length=1, max_length=64)
    quantity: int = Field(..., ge=1, le=500, description="生产数量（≥1）")
    image_generation_route: str = Field(default="CODEX", pattern="^(API|CODEX)$")
    style_code: str | None = Field(default=None, max_length=64)
    palette_code: str | None = Field(default=None, max_length=32)


class BatchSummary(BaseModel):
    id: str
    product_type_id: str
    requested_quantity: int
    image_generation_route: str
    control_state: str
    request_key: str
    input_snapshot_hash: str
    usage_code: str
    style_code: str | None = None
    palette_code: str | None = None
    prepared_at: datetime | None = None
    created_at: datetime


class BatchItem(BaseModel):
    id: str
    product_id: str
    internal_sku: str
    revision_id: str
    revision_status: str
    image_progress: dict


class BatchDetailResponse(BaseModel):
    batch: BatchSummary
    items: list[BatchItem]
    counts: dict


class PrepareResponse(BaseModel):
    batch_id: str
    prepared_count: int
    skipped_count: int
    plan_count: int
    errors: list[dict[str, str]]
