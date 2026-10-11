"""时间工具（叶子模块，避免与 models 形成循环导入）。"""

from __future__ import annotations

from datetime import datetime, timezone


def utc_now() -> datetime:
    """统一的 UTC 当前时间（所有时间戳均以此为准）。"""
    return datetime.now(timezone.utc)
