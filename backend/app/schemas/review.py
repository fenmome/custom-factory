"""人工复审 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, Field, model_validator

from app.schemas.common import OperationKeyMixin

REVIEW_REASON_CODES = (
    "PRODUCT_MISMATCH",
    "ROLE_MISMATCH",
    "CONCEPT_INCONSISTENCY",
    "TEXT_ERROR",
    "VISUAL_DEFECT",
    "OTHER",
)


class DecisionMandate(BaseModel):
    """单个近期变更来源，用于审计回溯。"""

    source: str | None = Field(default=None, max_length=64)
    note: str | None = Field(default=None, max_length=1000)


class ReviewDecisionIn(BaseModel):
    slot: int = Field(..., ge=1, le=8)
    decision: str = Field(..., pattern="^(PASS|FAIL)$")
    reason_code: str | None = None
    note: str | None = Field(default=None, max_length=1000)
    mandate: DecisionMandate | None = None

    @model_validator(mode="after")
    def _validate_reason(self) -> "ReviewDecisionIn":
        if self.decision == "FAIL":
            if self.reason_code is None:
                raise ValueError("标记问题必须选择原因码")
            if self.reason_code not in REVIEW_REASON_CODES:
                raise ValueError(f"未知原因码 {self.reason_code}")
            if self.reason_code == "OTHER" and not (self.note or "").strip():
                raise ValueError("原因码 OTHER 必须填写说明")
        return self


class SnapshotItemIn(BaseModel):
    asset_id: str
    checksum: str


class ReviewSubmitRequest(OperationKeyMixin):
    decisions: list[ReviewDecisionIn] = Field(default_factory=list)
    snapshot: list[SnapshotItemIn] = Field(default_factory=list)
    complete_set: bool = False


class ReviewItem(BaseModel):
    slot: int
    role: str
    is_required: bool
    asset_id: str | None = None
    checksum: str | None = None
    width: int | None = None
    height: int | None = None
    byte_size: int | None = None
    integrity_state: str | None = None
    technical: dict | None = None
    semantic: dict | None = None
    human: dict | None = None
    ocr: dict | None = None
    effective: str
    history: list[dict] = Field(default_factory=list)


class ReviewView(BaseModel):
    product_id: str
    internal_sku: str
    revision_id: str
    revision_status: str
    brand_name: str | None = None
    object: str | None = None
    title_text: str | None = None
    items: list[ReviewItem]
    snapshot: list[SnapshotItemIn]
