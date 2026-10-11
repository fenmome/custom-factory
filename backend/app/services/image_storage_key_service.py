"""图片存储键生成。

路径规则（资源摘录 12.3）：
```
<PREFIX>/<SKU>/<SKU>-<slot:02d>.png                 # 首个修订
<PREFIX>/<SKU>/revisions/<rev_id>/<SKU>-<slot:02d>.png  # 后续修订
```
数据库只存 storage_key，绝不存绝对路径。
"""

from __future__ import annotations


def build_storage_key(
    *,
    prefix: str,
    sku: str,
    slot: int,
    revision_number: int = 1,
    revision_id: str | None = None,
) -> str:
    filename = f"{sku}-{slot:02d}.png"
    if revision_number <= 1:
        return f"{prefix}/{sku}/{filename}"
    suffix = revision_id or f"rev{revision_number:02d}"
    return f"{prefix}/{sku}/revisions/{suffix}/{filename}"


def parse_slot_from_key(storage_key: str) -> int | None:
    try:
        filename = storage_key.rsplit("/", 1)[-1]
        slot_part = filename.rsplit("-", 1)[-1].split(".")[0]
        return int(slot_part)
    except (IndexError, ValueError):
        return None
