"""模型基类与公共类型别名。

约定：
- 主键统一 `CHAR(36)` UUID v4
- 时间戳统一 UTC `DATETIME(6)`
"""

from __future__ import annotations

from datetime import datetime, timezone

from sqlalchemy import ForeignKey, String, func
from sqlalchemy.orm import DeclarativeBase, Mapped, mapped_column
from sqlalchemy.types import CHAR, DateTime


class Base(DeclarativeBase):
    """所有 ORM 模型的声明基类。"""


UUIDType = CHAR(36)
HASH_TYPE = CHAR(64)


def utc_now() -> datetime:
    return datetime.now(timezone.utc)


class TimestampMixin:
    """统一的 UTC 创建 / 更新时间。"""

    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        nullable=False,
    )
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        server_default=func.now(),
        onupdate=func.now(),
        nullable=False,
    )


def uuid_fk(
    *,
    target: str,
    ondelete: str = "RESTRICT",
    nullable: bool = False,
    index: bool = True,
    name: str | None = None,
) -> Mapped[str]:
    """CHAR(36) 外键列快捷构造。"""
    return mapped_column(
        CHAR(36),
        ForeignKey(target, ondelete=ondelete),
        nullable=nullable,
        index=index,
        name=name,
    )


def str_col(length: int, **kwargs) -> Mapped[str]:
    return mapped_column(String(length), **kwargs)
