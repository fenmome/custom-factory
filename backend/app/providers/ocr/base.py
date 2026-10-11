"""OCR 提供者抽象。"""

from __future__ import annotations

from abc import ABC, abstractmethod
from dataclasses import dataclass, field


@dataclass(frozen=True)
class OcrRegion:
    text: str
    x: int
    y: int
    width: int
    height: int
    confidence: float = 0.0


@dataclass(frozen=True)
class OcrResult:
    texts: list[str] = field(default_factory=list)
    regions: list[OcrRegion] = field(default_factory=list)


class OcrProvider(ABC):
    """OCR 引擎抽象接口。"""

    @abstractmethod
    def extract(self, *, storage_key: str) -> OcrResult:
        """从存储对象中提取文字。"""
