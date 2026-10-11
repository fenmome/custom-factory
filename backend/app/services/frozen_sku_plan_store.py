"""冻结 SKU 计划存储。

路径：`<plan_root>/<workspace_id>/<revision_id>.json`
格式：`{"package": {...}, "sha256": "..."}`
"""

from __future__ import annotations

import json
from pathlib import Path
from typing import Any

from app.config import settings
from app.core.exceptions import ResourceIntegrityError
from app.core.hashing import sha256_hex


class FrozenSkuPlanStore:
    def __init__(self, *, root: Path | None = None) -> None:
        self.root = root or settings.plan_store_root_path

    def _path(self, *, workspace_id: str, revision_id: str) -> Path:
        return self.root / workspace_id / f"{revision_id}.json"

    def save(self, *, workspace_id: str, revision_id: str, package: dict[str, Any]) -> str:
        """写入冻结计划信封 `{"package": {...}, "sha256": "..."}`。"""
        digest = sha256_hex(package)
        envelope = {"package": package, "sha256": digest}
        target = self._path(workspace_id=workspace_id, revision_id=revision_id)
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(
            json.dumps(envelope, ensure_ascii=False, sort_keys=True, indent=2), encoding="utf-8"
        )
        return digest

    def load(self, *, workspace_id: str, revision_id: str) -> dict[str, Any] | None:
        target = self._path(workspace_id=workspace_id, revision_id=revision_id)
        if not target.exists():
            return None
        return json.loads(target.read_text(encoding="utf-8"))

    def verify(self, *, workspace_id: str, revision_id: str) -> bool:
        plan = self.load(workspace_id=workspace_id, revision_id=revision_id)
        if plan is None:
            return False
        package = plan.get("package")
        declared = plan.get("sha256")
        if package is None or declared is None:
            return False
        return sha256_hex(package) == declared

    def delete(self, *, workspace_id: str, revision_id: str) -> None:
        target = self._path(workspace_id=workspace_id, revision_id=revision_id)
        if target.exists():
            target.unlink()

    def require(self, *, workspace_id: str, revision_id: str) -> dict[str, Any]:
        plan = self.load(workspace_id=workspace_id, revision_id=revision_id)
        if plan is None:
            raise ResourceIntegrityError(detail=f"冻结计划缺失: revision={revision_id}")
        return plan
