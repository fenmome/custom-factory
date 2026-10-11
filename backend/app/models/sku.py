"""SKU 配置表（产品类型 → 前缀 + 定宽流水号）。"""

from __future__ import annotations

from sqlalchemy import Boolean, Integer, String, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import UUIDType, Base, TimestampMixin


class ProductTypeSkuConfig(Base, TimestampMixin):
    """产品类型 SKU 配置。

    规则：
    - 前缀一经使用永久归属该产品类型（不可被其它类型复用）
    - 流水号从 1 开始，不回绕
    - `000000` 无效
    """

    __tablename__ = "product_type_sku_configs"
    __table_args__ = (UniqueConstraint("workspace_id", "product_type_code", name="uk_ws_product_type"),)

    id: Mapped[str] = mapped_column(UUIDType, primary_key=True)
    workspace_id: Mapped[str] = mapped_column(UUIDType, nullable=False, index=True)
    product_type_code: Mapped[str] = mapped_column(String(64), nullable=False)
    display_name: Mapped[str] = mapped_column(String(255), nullable=False)
    prefix: Mapped[str] = mapped_column(String(32), nullable=False, unique=True)
    sequence_width: Mapped[int] = mapped_column(Integer, nullable=False, default=6, server_default="6")
    last_sequence: Mapped[int] = mapped_column(Integer, nullable=False, default=0, server_default="0")
    is_enabled: Mapped[bool] = mapped_column(Boolean, nullable=False, default=True, server_default="1")
