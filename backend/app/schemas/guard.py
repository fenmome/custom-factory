"""生产保护 Schema。"""

from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel


class PauseBrief(BaseModel):
    id: str
    scope_kind: str
    target: dict
    state: str
    trigger_rule_id: str
    rule_text: str
    reason: str
    paused_at: str | None = None
    updated_at: str | None = None
    trial_sku_limit: int
    trial_claim_count: int
    trial_completed_count: int
    trial_pass_count: int
    trial_fail_count: int


class GuardEvaluationBrief(BaseModel):
    level: str
    rule_id: str | None = None
    reason: str | None = None
    metrics: dict


class GuardStatusResponse(BaseModel):
    level: str
    evaluation: GuardEvaluationBrief
    pauses: list[PauseBrief]
    rules: dict


class TrialStartRequest(BaseModel):
    pass


class ClaimBrief(BaseModel):
    claim_id: str
    revision_id: str
    product_id: str
    internal_sku: str
    batch_id: str
    executor_kind: str
    executor_id: str
    last_activity_at: datetime


class ClaimListResponse(BaseModel):
    items: list[ClaimBrief]
    total: int
