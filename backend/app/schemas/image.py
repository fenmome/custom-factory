"""图片 Schema。"""

from __future__ import annotations

from pydantic import BaseModel


class QaBrief(BaseModel):
    result: str
    reason_code: str | None = None
    reason_detail: str | None = None
    evaluated_at: str | None = None


class ImageUploadResponse(BaseModel):
    slot: int
    role: str
    job_state: str
    attempt_id: str
    asset_id: str
    storage_key: str
    checksum: str
    byte_size: int
    width: int
    height: int
    technical: QaBrief
    semantic: QaBrief


class ProductImageView(BaseModel):
    slot: int
    role: str
    is_required: bool
    job_state: str
    asset_id: str | None = None
    checksum: str | None = None
    width: int | None = None
    height: int | None = None
    integrity_state: str | None = None
    effective_result: str | None = None
    technical: QaBrief | None = None
    semantic: QaBrief | None = None
    human: QaBrief | None = None
    ocr: QaBrief | None = None
