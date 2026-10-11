"""UUID v4 生成器（全局 CHAR(36) 主键统一由此产出）。"""

from __future__ import annotations

import uuid


def new_uuid() -> str:
    return str(uuid.uuid4())
