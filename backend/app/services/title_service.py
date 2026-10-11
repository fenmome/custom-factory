"""标题分配服务：AVAILABLE → RESERVED → USED。

- 绑定基于 Concept 的语义指纹（core_hash）
- READY 首次成功消耗 1 个 TitleUsage，后续修订不再消耗
- 为防止并发重复占用，采用有序扫描 + 行锁
"""

from __future__ import annotations

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.core.events import TITLE_USED, record_event, utc_now
from app.core.exceptions import TitlePoolExhaustedError, TitleReservationNotFoundError
from app.models.title import TitleAsset, TitleReservation, TitleUsage
from app.services.uuid_provider import new_uuid

APPROVED_STATUS = "CONTENT_QUALITY_APPROVED"


def _next_available(session: Session, *, pool_version: str, used_title_ids: set[str]) -> TitleAsset | None:
    stmt = (
        select(TitleAsset)
        .where(
            TitleAsset.editorial_status == APPROVED_STATUS,
            TitleAsset.pool_version == pool_version,
        )
        .order_by(TitleAsset.id)
    )
    for asset in session.execute(stmt.execution_options(yield_per=200)).scalars():
        if asset.id in used_title_ids:
            continue
        # 行级锁，确保并发下同一标题只被一个 SKU 占用
        locked = session.scalar(select(TitleAsset).where(TitleAsset.id == asset.id).with_for_update())
        if locked is not None:
            return locked
    return None


def reserve_for_revision(
    *,
    session: Session,
    workspace_id: str,
    product_id: str,
    revision_id: str,
    core_hash: str,
    request_key: str,
    pool_version: str,
) -> TitleReservation:
    """为一个修订预留一个标题（幂等：同一 product_id 已有预留则直接返回）。"""
    existing = session.scalar(
        select(TitleReservation).where(TitleReservation.product_id == product_id)
    )
    if existing is not None:
        if existing.revision_id != revision_id:
            existing.revision_id = revision_id
            session.flush()
        return existing

    used_title_ids = set(
        session.scalars(select(TitleReservation.title_id).where(TitleReservation.workspace_id == workspace_id)).all()
    )

    asset = _next_available(session, pool_version=pool_version, used_title_ids=used_title_ids)
    if asset is None:
        raise TitlePoolExhaustedError(detail=f"pool_version={pool_version} 已无可用已审批标题")

    reservation = TitleReservation(
        id=new_uuid(),
        workspace_id=workspace_id,
        product_id=product_id,
        revision_id=revision_id,
        title_id=asset.id,
        request_key=request_key,
        state="RESERVED",
        reserved_at=utc_now(),
    )
    session.add(reservation)
    session.flush()
    return reservation


def consume_usage(
    *,
    session: Session,
    workspace_id: str,
    product_id: str,
    revision_id: str,
    operation_key: str,
) -> TitleUsage | None:
    """首次 READY 成功时消费标题。若该 product 已消费过则不重复消耗。"""
    already = session.scalar(select(TitleUsage).where(TitleUsage.product_id == product_id))
    if already is not None:
        return None

    reservation = session.scalar(
        select(TitleReservation).where(TitleReservation.product_id == product_id)
    )
    if reservation is None:
        raise TitleReservationNotFoundError(detail=f"product_id={product_id}")

    asset = session.get(TitleAsset, reservation.title_id)
    if asset is None:
        raise TitleReservationNotFoundError(detail=f"title_id={reservation.title_id}")

    usage = TitleUsage(
        id=new_uuid(),
        workspace_id=workspace_id,
        product_id=product_id,
        revision_id=revision_id,
        title_id=asset.id,
        title_text=asset.title_text,
        operation_key=operation_key,
        used_at=utc_now(),
    )
    session.add(usage)

    reservation.state = "USED"
    reservation.used_at = utc_now()
    session.flush()

    record_event(
        session,
        workspace_id=workspace_id,
        entity_type="PRODUCT",
        entity_id=product_id,
        event_kind=TITLE_USED,
        payload={"title_id": asset.id, "revision_id": revision_id},
    )
    return usage


def release(*, session: Session, workspace_id: str, product_id: str) -> TitleReservation | None:
    reservation = session.scalar(
        select(TitleReservation).where(
            TitleReservation.workspace_id == workspace_id,
            TitleReservation.product_id == product_id,
        )
    )
    if reservation is None:
        return None
    if reservation.state == "USED":
        return reservation
    reservation.state = "RELEASED"
    reservation.released_at = utc_now()
    session.flush()
    return reservation


def title_text_of(*, session: Session, title_id: str) -> str | None:
    asset = session.get(TitleAsset, title_id)
    return asset.title_text if asset else None


def bulk_mark_reservations_used(*, session: Session, product_ids: list[str]) -> int:
    """批量标记（仅用于数据修复），返回影响行数。"""
    if not product_ids:
        return 0
    result = session.execute(
        update(TitleReservation)
        .where(TitleReservation.product_id.in_(product_ids), TitleReservation.state == "RESERVED")
        .values(state="USED", used_at=utc_now())
    )
    return int(result.rowcount or 0)
