"""OCR 提供者注册表（运行时可选依赖，延迟导入）。"""

from __future__ import annotations

from functools import lru_cache

from app.config import settings
from app.core.exceptions import OCRRuntimeError
from app.providers.ocr.base import OcrProvider
from app.providers.ocr.noop import NoopOcrProvider


@lru_cache(maxsize=1)
def get_ocr_provider() -> OcrProvider:
    if not settings.OCR_ENABLED:
        return NoopOcrProvider()
    try:
        from paddleocr import PaddleOCR  # noqa: PLC0415 - 可选依赖

        return PaddleOcrProvider(engine=PaddleOCR(use_angle_cls=True, lang="en"))
    except Exception as exc:  # noqa: BLE001
        raise OCRRuntimeError(detail=f"PaddleOCR 运行时不可用: {exc}") from exc


class PaddleOcrProvider(OcrProvider):
    """PaddleOCR 本地运行时适配。"""

    def __init__(self, *, engine) -> None:  # noqa: ANN001
        self.engine = engine

    def extract(self, *, storage_key: str) -> OcrProvider:  # type: ignore[override]
        from app.core.storage import storage
        from app.providers.ocr.base import OcrRegion, OcrResult

        path = storage.get_path(key=storage_key)
        raw = self.engine.ocr(str(path), cls=True)
        texts: list[str] = []
        regions: list[OcrRegion] = []
        for page in raw or []:
            for box, (text, confidence) in page:
                xs = [point[0] for point in box]
                ys = [point[1] for point in box]
                texts.append(text)
                regions.append(
                    OcrRegion(
                        text=text,
                        x=int(min(xs)),
                        y=int(min(ys)),
                        width=int(max(xs) - min(xs)),
                        height=int(max(ys) - min(ys)),
                        confidence=float(confidence),
                    )
                )
        return OcrResult(texts=texts, regions=regions)
