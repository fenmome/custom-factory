"""幂等控制。

创建类操作必须携带 `operation_key`（UUID v4），服务端按
`(workspace_id, operation_key, scope)` 去重，重复请求返回首次结果。
"""

from __future__ import annotations

from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.exceptions import IdempotencyConflictError, IdempotencyReplay
from app.core.hashing import sha256_hex
from app.models.audit import IdempotencyRecord


def request_fingerprint(payload: dict[str, Any]) -> str:
    """计算请求体指纹，用于检测“同 key 不同内容”的非法重放。"""
    return sha256_hex(payload)


def begin(
    session: Session,
    *,
    workspace_id: str,
    operation_key: str,
    scope: str,
    payload: dict[str, Any],
) -> None:
    """登记幂等键。

    - 已存在且指纹一致 → IdempotencyReplay（返回首次结果）
    - 已存在但指纹不同 → IdempotencyConflictError（拒绝，避免脏请求被静默吞掉）
    """
    fingerprint = request_fingerprint(payload)
    existing = session.scalar(
        select(IdempotencyRecord).where(
            IdempotencyRecord.workspace_id == workspace_id,
            IdempotencyRecord.operation_key == operation_key,
            IdempotencyRecord.scope == scope,
        )
    )
    if existing is not None:
        if existing.request_fingerprint != fingerprint:
            raise IdempotencyConflictError(detail=f"operation_key={operation_key} 的请求内容与首次提交不一致")
        raise IdempotencyReplay(detail=existing.response_snapshot)

    record = IdempotencyRecord(
        workspace_id=workspace_id,
        operation_key=operation_key,
        scope=scope,
        request_fingerprint=fingerprint,
        response_snapshot={},
    )
    session.add(record)
    try:
        session.flush()
    except IntegrityError as exc:
        session.rollback()
        raise IdempotencyReplay from exc


def complete(
    session: Session,
    *,
    workspace_id: str,
    operation_key: str,
    scope: str,
    response_snapshot: dict[str, Any],
) -> None:
    from sqlalchemy import update

    session.execute(
        update(IdempotencyRecord)
        .where(
            IdempotencyRecord.workspace_id == workspace_id,
            IdempotencyRecord.operation_key == operation_key,
            IdempotencyRecord.scope == scope,
        )
        .values(response_snapshot=response_snapshot)
    )
