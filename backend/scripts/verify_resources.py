"""重新生成业务资源的 SHA-256 清单（app/resources/MANIFEST.json）。

用法： `python -m scripts.verify_resources`
"""

from __future__ import annotations

import json
from pathlib import Path

from app.core.resource_loader import RESOURCES_ROOT, iter_manifest


def main() -> None:
    entries = iter_manifest()
    manifest_path = RESOURCES_ROOT / "MANIFEST.json"
    manifest_path.write_text(
        json.dumps({"version": 1, "resources": entries}, ensure_ascii=False, indent=2) + "\n",
        encoding="utf-8",
    )
    print(f"已写入 {manifest_path} ({len(entries)} 个资源)")
    for item in entries:
        print(f"  {item['sha256'][:16]}…  {item['path']}")


if __name__ == "__main__":
    Path(__file__).resolve()  # 占位，保持模块可执行语义清晰
    main()
