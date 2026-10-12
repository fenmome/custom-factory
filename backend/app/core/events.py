"""生命周期审计事件。

所有关键状态迁移都会追加一条 LifecycleEvent（追加式，从不修改/删除）。
业务的 `state` 字段由模型自己的 `updated_at` 负责，这里记录不可变流水。
"""

from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy.orm import Session

from app.core.time_utils import utc_now
from app.models.audit import LifecycleEvent

# 事件类型常量（避免各处硬编码字符串散落）
BATCH_CREATED = "BATCH_CREATED"
BATCH_PREPARED = "BATCH_PREPARED"
SKU_ALLOCATED = "SKU_ALLOCATED"
TITLE_RESERVED = "TITLE_RESERVED"
TITLE_USED = "TITLE_USED"
CONCEPT_FROZEN = "CONCEPT_FROZEN"
IMAGE_JOBS_CREATED = "IMAGE_JOBS_CREATED"
IMAGE_ASSET_REGISTERED = "IMAGE_ASSET_REGISTERED"
IMAGE_QA_RECORDED = "IMAGE_QA_RECORDED"
HUMAN_REVIEW_SUBMITTED = "HUMAN_REVIEW_SUBMITTED"
REVISION_READY = "REVISION_READY"
GUARD_PAUSED = "GUARD_PAUSED"
GUARD_TRIAL_STARTED = "GUARD_TRIAL_STARTED"
GUARD_TRIAL_EVALUATED = "GUARD_TRIAL_EVALUATED"
GUARD_RESOLVED = "GUARD_RESOLVED"
GUARD_YELLOW = "GUARD_YELLOW"
SYSTEM_EXCEPTION = "SYSTEM_EXCEPTION"


def record_event(
    session: Session,
    *,
    workspace_id: str,
    entity_type: str,
    entity_id: str,
    event_kind: str,
    payload: dict[str, Any] | None = None,
    occurred_at: datetime | None = None,
) -> LifecycleEvent:
    """写入一条审计事件（调用方负责事务提交）。"""
    event = LifecycleEvent(
        workspace_id=workspace_id,
        entity_type=entity_type,
        entity_id=entity_id,
        event_kind=event_kind,
        payload=payload or {},
        occurred_at=occurred_at or utc_now(),
    )
    session.add(event)
    return event


def list_events(
    session: Session,
    *,
    workspace_id: str,
    entity_type: str | None = None,
    entity_id: str | None = None,
    limit: int = 100,
) -> list[LifecycleEvent]:
    from sqlalchemy import select

    stmt = select(LifecycleEvent).where(LifecycleEvent.workspace_id == workspace_id)
    if entity_type:
        stmt = stmt.where(LifecycleEvent.entity_type == entity_type)
    if entity_id:
        stmt = stmt.where(LifecycleEvent.entity_id == entity_id)
    stmt = stmt.order_by(LifecycleEvent.id.desc()).limit(limit)
    return list(session.scalars(stmt).all())
