"""Canonical JSON (CF-CJSON-V1) 与 SHA-256 工具。

所有业务快照、冻结计划、QA 规则指纹都通过这里产出，保证跨平台跨平台一致
（Windows CRLF 问题通过统一 LF + 排序键解决）。
"""

from __future__ import annotations

import hashlib
import json
from typing import Any

CANONICAL_JSON_VERSION = "CF-CJSON-V1"
_HASH_CHUNK = 1 << 16


def canonical_json_bytes(payload: Any) -> bytes:
    """序列化为规范 JSON 字节。

    - 键按字典序排序
    - UTF-8 编码，`ensure_ascii=False` 但统一不转义非 ASCII 之外的字符
    - 分隔符固定为 `,` 与 `:`，无尾随空格
    - 换行策略统一 LF（不依赖平台行尾）
    """
    text = json.dumps(
        payload,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
        default=str,
    )
    return text.encode("utf-8")


def sha256_hex(payload: Any) -> str:
    """对任意可序列化对象计算 SHA-256 十六进制摘要。"""
    if isinstance(payload, (bytes, bytearray)):
        data = bytes(payload)
    else:
        data = canonical_json_bytes(payload)
    return hashlib.sha256(data).hexdigest()


def sha256_file(path: str) -> str:
    digest = hashlib.sha256()
    with open(path, "rb") as handle:
        while True:
            chunk = handle.read(_HASH_CHUNK)
            if not chunk:
                break
            digest.update(chunk)
    return digest.hexdigest()


def core_hash(*parts: str) -> str:
    """组合多个业务片段生成语义指纹（core_hash）。"""
    joined = "\x1f".join(part if part is not None else "" for part in parts)
    return hashlib.sha256(joined.encode("utf-8")).hexdigest()


def stable_payload_hash(payload: dict[str, Any], *, exclude_keys: tuple[str, ...] = ()) -> str:
    """对字典做稳定哈希，可排除易变字段（如时间戳）。"""
    cleaned = {k: v for k, v in payload.items() if k not in exclude_keys}
    return sha256_hex(cleaned)
