"""业务资源加载器。

硬性要求：所有业务规则必须从 `app/resources/**.json` 加载，禁止在代码中硬编码。
每个资源加载时计算 SHA-256 内容哈希，业务把它写入 QA/ Revision 的 `rule_hash`
/ `policy_hash` / `schema_hash` 字段，实现内容寻址（content-addressed）。
"""

from __future__ import annotations

import json
from functools import lru_cache
from pathlib import Path
from typing import Any, TypeVar

from app.core.exceptions import ResourceIntegrityError
from app.core.hashing import sha256_hex

RESOURCES_ROOT = Path(__file__).resolve().parents[1] / "resources"

T = TypeVar("T")


class Resource:
    """带内容哈希的资源包装。"""

    def __init__(self, *, name: str, path: Path, data: dict[str, Any], content_hash: str) -> None:
        self.name = name
        self.path = path
        self.data = data
        self.content_hash = content_hash

    @property
    def rule_id(self) -> str:
        return str(self.data.get("rule_id") or self.data.get("policy_id") or self.data.get("schema_id") or self.name)

    @property
    def version(self) -> str:
        return str(self.data.get("version") or self.data.get("binding_version") or "")

    def __getitem__(self, key: str) -> Any:
        return self.data[key]

    def get(self, key: str, default: Any = None) -> Any:
        return self.data.get(key, default)


def _locate(*, relative_path: str) -> Path:
    candidate = RESOURCES_ROOT / relative_path
    if not candidate.is_file():
        raise ResourceIntegrityError(detail=f"资源文件缺失: {relative_path}")
    return candidate


@lru_cache(maxsize=64)
def load_resource(*, relative_path: str) -> Resource:
    """加载单个资源文件并缓存（含 content_hash）。"""
    path = _locate(relative_path=relative_path)
    try:
        raw = path.read_text(encoding="utf-8")
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        raise ResourceIntegrityError(detail=f"资源 JSON 解析失败 {relative_path}: {exc}") from exc
    if not isinstance(data, dict):
        raise ResourceIntegrityError(detail=f"资源根节点必须是对象: {relative_path}")
    return Resource(name=relative_path, path=path, data=data, content_hash=sha256_hex(data))


def load(*, relative_path: str) -> Resource:
    return load_resource(relative_path=relative_path)


# ---------------- 具名资源快捷访问 ----------------
@lru_cache(maxsize=1)
def prompt_rule() -> Resource:
    return load_resource(relative_path="prompt_rules/UV_DTF_PROMPT_RULE_V1_4.json")


@lru_cache(maxsize=1)
def image_policy() -> Resource:
    return load_resource(relative_path="image_policy/uv_dtf_image_policy_v1_2.json")


@lru_cache(maxsize=1)
def allowed_objects() -> Resource:
    return load_resource(relative_path="visual_prep/allowed_objects_v1.json")


@lru_cache(maxsize=1)
def visual_preparation() -> Resource:
    return load_resource(relative_path="visual_prep/visual_preparation_v1.json")


@lru_cache(maxsize=1)
def guard_rules() -> Resource:
    return load_resource(relative_path="guard_rules/production_guard_rules_v1.json")


@lru_cache(maxsize=1)
def product_profile() -> Resource:
    return load_resource(relative_path="profiles/product_profile_v1.json")


@lru_cache(maxsize=1)
def attribute_schema() -> Resource:
    return load_resource(relative_path="schemas/small_business_attribute_schema_v1.json")


@lru_cache(maxsize=1)
def title_source() -> Resource:
    return load_resource(relative_path="title_source/small_business_title_source_v1.json")


def iter_manifest() -> list[dict[str, Any]]:
    """遍历所有资源并产出清单条目（供 scripts/verify_resources 生成 MANIFEST.json）。

    注意：manifest 只做记录，**不做**强制校验——否则每次微调规则都要同时改两个文件。
    """
    entries: list[dict[str, Any]] = []
    for path in sorted(RESOURCES_ROOT.rglob("*.json")):
        relative = path.relative_to(RESOURCES_ROOT).as_posix()
        if relative == "MANIFEST.json":
            continue
        resource = load_resource(relative_path=relative)
        entries.append(
            {
                "path": relative,
                "rule_id": resource.rule_id,
                "version": resource.version,
                "sha256": resource.content_hash,
            }
        )
    return entries


def clear_cache() -> None:
    """测试用：清空资源缓存。"""
    load_resource.cache_clear()
    for fn in (prompt_rule, image_policy, allowed_objects, visual_preparation, guard_rules, product_profile, attribute_schema, title_source):
        fn.cache_clear()
