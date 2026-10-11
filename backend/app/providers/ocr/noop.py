"""占位 OCR 提供者：无本地 PaddleOCR 运行时时使用。"""

from __future__ import annotations

from app.providers.ocr.base import OcrProvider, OcrResult


class NoopOcrProvider(OcrProvider):
    def extract(self, *, storage_key: str) -> OcrResult:  # noqa: ARG002
        return OcrResult(texts=[], regions=[])
