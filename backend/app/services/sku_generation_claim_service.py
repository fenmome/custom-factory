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
    """领取下一个可执行的 SKU；返回 plan 或空结果。

    领取前检查：
    - SYSTEM 级暂停直接拒绝
    - 逐候选修订按其产品类型 / 执行器模型检查最小影响范围暂停（FR-09）
    - 处于 TRIAL_RUNNING 的暂停控制：领取数不得超过 trial_sku_limit
    """
    guard = production_guard_service.ProductionGuardService()
    paused = guard.is_paused(session=session, workspace_id=workspace_id)
    if paused is not None:
        raise ProductionPausedError(
            detail=f"{paused.scope_kind} 已暂停：{paused.reason}",
            code=41401,
        )

    active_pauses = list(guard.active_pauses(session=session, workspace_id=workspace_id))

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

        # 最小影响范围（FR-09）：候选 SKU 所属范围的暂停控制
        # - PAUSED → 跳过该候选（暂停范围内停止新领取，范围外正常）
        # - TRIAL_RUNNING → 领取数不得超过 trial_sku_limit，超限跳过
        scope_control = next(
            (
                c
                for c in active_pauses
                if c.scope_kind == production_guard_service.SCOPE_PRODUCT_TYPE
                and c.target.get("product_type_id") == batch.product_type_id
            ),
            None,
        )
        if scope_control is not None:
            if scope_control.state == "PAUSED":
                continue
            if int(scope_control.trial_claim_count) >= int(scope_control.trial_sku_limit):
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
        if scope_control is not None and scope_control.state == "TRIAL_RUNNING":
            scope_control.trial_claim_count = int(scope_control.trial_claim_count) + 1
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
