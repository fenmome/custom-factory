"""SKU 配置与原子分配服务。

规则（agent.md 4.1）：
- 格式：`前缀 + 定宽流水号`（如 DZUVDTF000001）
- 创建批次时在**同一数据库事务**内原子分配 N 个 SKU
- 前缀大写字母+数字，全局唯一，一旦使用永久归属该产品类型
- 流水号从 1 开始，不回绕，不同产品类型独立计数
- `000000` 无效，已分配 SKU 不可回收
"""

from __future__ import annotations

import re
from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import (
    ProductTypeDisabledError,
    ProductTypeNotFoundError,
    SkuPrefixConflictError,
    SkuSequenceWidthTooSmallError,
    ValidationError,
)
from app.models.sku import ProductTypeSkuConfig
from app.services.uuid_provider import new_uuid

PREFIX_PATTERN = re.compile(r"^[A-Z0-9]{1,32}$")


def format_sku(*, prefix: str, sequence: int, width: int) -> str:
    """格式化 SKU。`000000` 视为无效。"""
    if sequence <= 0:
        raise ValidationError(detail="流水号必须从 1 开始")
    if width <= 0:
        raise ValidationError(detail="流水号位数必须为正整数")
    rendered = str(sequence).rjust(width, "0")
    if int(rendered) == 0:
        raise ValidationError(detail="000000 无效")
    return f"{prefix}{rendered}"


def validate_prefix(prefix: str) -> str:
    candidate = prefix.strip().upper()
    if not PREFIX_PATTERN.match(candidate):
        raise ValidationError(detail="SKU 前缀只能包含大写字母与数字，长度 1-32")
    return candidate


def get_config(*, session: Session, workspace_id: str, product_type_code: str) -> ProductTypeSkuConfig:
    config = session.scalar(
        select(ProductTypeSkuConfig).where(
            ProductTypeSkuConfig.workspace_id == workspace_id,
            ProductTypeSkuConfig.product_type_code == product_type_code,
        )
    )
    if config is None:
        raise ProductTypeNotFoundError(detail=f"product_type_code={product_type_code}")
    return config


def ensure_usable(*, config: ProductTypeSkuConfig) -> None:
    if not config.is_enabled:
        raise ProductTypeDisabledError(detail=f"产品类型 {config.product_type_code} 已停用")


def allocate_sequence_block(
    *,
    session: Session,
    config: ProductTypeSkuConfig,
    quantity: int,
) -> list[tuple[str, int, str]]:
    """在同一事务内原子锁定并递增计数器，返回 `[(sku, sequence, prefix), ...]`。

    使用 `with_for_update()` 行锁防止并发批次分配重复流水号。
    """
    if quantity <= 0:
        raise ValidationError(detail="quantity 必须为正整数")

    locked = session.scalar(
        select(ProductTypeSkuConfig).where(ProductTypeSkuConfig.id == config.id).with_for_update()
    )
    if locked is None:
        raise ProductTypeNotFoundError

    start = locked.last_sequence + 1
    end = locked.last_sequence + quantity

    results: list[tuple[str, int, str]] = []
    for sequence in range(start, end + 1):
        results.append((format_sku(prefix=locked.prefix, sequence=sequence, width=locked.sequence_width), sequence, locked.prefix))

    locked.last_sequence = end
    session.flush()
    return results


def create_config(
    *,
    session: Session,
    workspace_id: str,
    product_type_code: str,
    display_name: str,
    prefix: str,
    sequence_width: int = 6,
) -> ProductTypeSkuConfig:
    prefix = validate_prefix(prefix)
    if sequence_width < 1 or sequence_width > 12:
        raise ValidationError(detail="流水号位数范围 1-12")

    conflict = session.scalar(select(ProductTypeSkuConfig).where(ProductTypeSkuConfig.prefix == prefix))
    if conflict is not None and conflict.product_type_code != product_type_code:
        raise SkuPrefixConflictError(detail=f"前缀 {prefix} 已归属 {conflict.product_type_code}")

    existing = session.scalar(
        select(ProductTypeSkuConfig).where(
            ProductTypeSkuConfig.workspace_id == workspace_id,
            ProductTypeSkuConfig.product_type_code == product_type_code,
        )
    )
    if existing is not None:
        return existing

    config = ProductTypeSkuConfig(
        id=new_uuid(),
        workspace_id=workspace_id,
        product_type_code=product_type_code,
        display_name=display_name,
        prefix=prefix,
        sequence_width=sequence_width,
        last_sequence=0,
        is_enabled=True,
    )
    session.add(config)
    session.flush()
    return config


def update_config(
    *,
    session: Session,
    config: ProductTypeSkuConfig,
    display_name: str | None = None,
    sequence_width: int | None = None,
    is_enabled: bool | None = None,
) -> ProductTypeSkuConfig:
    if sequence_width is not None and sequence_width < len(str(config.last_sequence)):
        raise SkuSequenceWidthTooSmallError(
            detail=f"当前最大流水号 {config.last_sequence} 需要至少 {len(str(config.last_sequence))} 位"
        )
    if display_name is not None:
        config.display_name = display_name
    if sequence_width is not None:
        config.sequence_width = sequence_width
    if is_enabled is not None:
        config.is_enabled = is_enabled
    session.flush()
    return config


def list_configs(*, session: Session, workspace_id: str) -> Sequence[ProductTypeSkuConfig]:
    return session.scalars(
        select(ProductTypeSkuConfig)
        .where(ProductTypeSkuConfig.workspace_id == workspace_id)
        .order_by(ProductTypeSkuConfig.product_type_code)
    ).all()
