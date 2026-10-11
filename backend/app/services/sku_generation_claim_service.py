"""SKU 领取协调（FR-07 路线 B）。

约束：
- 同一 SKU 由同一执行器、同一会话完成
- 支持跨批次公平领取
- 领取前必须检查生产保护暂停
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.events import utc_now
from app.core.exceptions import ProductionPausedError
from app.models.guard import ProductionPauseControl, SkuGenerationClaim
from app.models.product import Batch, Product, ProductRevision
from app.services import production_guard_service
from app.services.uuid_provider import new_uuid

ACTIVE_STATES = ("ACTIVE",)


def _eligible_revision_query(*, workspace_id: str, batch_id: str | None):
    stmt = (
        select(ProductRevision)
        .join(Batch, ProductRevision.batch_id == Batch.id)
        .where(
            ProductRevision.workspace_id == workspace_id,
            ProductRevision.status != "READY_FOR_PUBLISH",
            Batch.control_state == "ACTIVE",
        )
    )
    if batch_id:
        stmt = stmt.where(ProductRevision.batch_id == batch_id)
    # 公平领取：按批次创建时间 + 修订顺序
    stmt = stmt.order_by(Batch.created_at, ProductRevision.created_at)
    return stmt


def claim(
    *,
    session: Session,
    workspace_id: str,
    executor_kind: str,
    executor_id: str,
    request_key: str,
    batch_id: str | None = None,
) -> dict:
    """领取下一个可执行的 SKU；返回 plan 或空结果。"""
    guard = production_guard_service.ProductionGuardService()
    paused = guard.is_paused(session=session, workspace_id=workspace_id)
    if paused is not None:
        raise ProductionPausedError(
            detail=f"{paused.scope_kind} 已暂停：{paused.reason}",
            code=41401,
        )

    stmt = _eligible_revision_query(workspace_id=workspace_id, batch_id=batch_id)
    for revision in session.scalars(stmt).all():
        existing_active = session.scalar(
            select(SkuGenerationClaim).where(
                SkuGenerationClaim.revision_id == revision.id,
                SkuGenerationClaim.state == "ACTIVE",
            )
        )
        if existing_active is not None:
            continue

        product = session.get(Product, revision.product_id)
        batch = session.get(Batch, revision.batch_id)
        if product is None or batch is None:
            continue

        claim_row = SkuGenerationClaim(
            id=new_uuid(),
            workspace_id=workspace_id,
            revision_id=revision.id,
            product_id=product.id,
            batch_id=batch.id,
            executor_kind=executor_kind,
            executor_id=executor_id,
            state="ACTIVE",
            request_key=request_key,
            last_activity_at=utc_now(),
            created_at=utc_now(),
        )
        session.add(claim_row)
        session.flush()
        return {
            "claim_id": claim_row.id,
            "revision_id": revision.id,
            "product_id": product.id,
            "internal_sku": product.internal_sku,
            "batch_id": batch.id,
            "executor_kind": executor_kind,
            "executor_id": executor_id,
        }

    return {}


def heartbeat(*, session: Session, workspace_id: str, claim_id: str) -> SkuGenerationClaim | None:
    claim_row = session.scalar(
        select(SkuGenerationClaim).where(
            SkuGenerationClaim.workspace_id == workspace_id, SkuGenerationClaim.id == claim_id
        )
    )
    if claim_row is None:
        return None
    claim_row.last_activity_at = utc_now()
    session.flush()
    return claim_row


def close(*, session: Session, workspace_id: str, claim_id: str) -> SkuGenerationClaim | None:
    claim_row = session.scalar(
        select(SkuGenerationClaim).where(
            SkuGenerationClaim.workspace_id == workspace_id, SkuGenerationClaim.id == claim_id
        )
    )
    if claim_row is None:
        return None
    claim_row.state = "CLOSED"
    claim_row.last_activity_at = utc_now()
    session.flush()
    return claim_row


def active_claims(*, session: Session, workspace_id: str) -> list[SkuGenerationClaim]:
    return list(
        session.scalars(
            select(SkuGenerationClaim)
            .where(SkuGenerationClaim.workspace_id == workspace_id, SkuGenerationClaim.state == "ACTIVE")
            .order_by(SkuGenerationClaim.last_activity_at.desc())
        ).all()
    )


def count_active(*, session: Session, workspace_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(SkuGenerationClaim)
            .where(SkuGenerationClaim.workspace_id == workspace_id, SkuGenerationClaim.state == "ACTIVE")
        )
        or 0
    )


def pause_for_batches(*, session: Session, workspace_id: str) -> list[ProductionPauseControl]:
    return list(production_guard_service.ProductionGuardService.active_pauses(session=session, workspace_id=workspace_id))
