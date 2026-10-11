"""PNG 字节检查（只读，绝不修改原图）。

约束（feature spec 12.2）：
- 仅 PNG
- 正方形，宽高各 ≥1200
- 无透明像素（TRANSPARENCY_EXPECTED = False）
- 禁止任何缩放 / 裁剪 / 重压缩 —— 本模块只用 Pillow 做**读取**。
"""

from __future__ import annotations

import io
from dataclasses import dataclass

from PIL import Image

PNG_MAGIC = b"\x89PNG\r\n\x1a\n"


@dataclass(frozen=True)
class ImageProbe:
    is_png: bool
    width: int
    height: int
    has_alpha: bool
    has_transparent_pixel: bool
    readable: bool
    error: str | None = None


def sniff_is_png(data: bytes) -> bool:
    return data[:8] == PNG_MAGIC


def probe(data: bytes) -> ImageProbe:
    """读取 PNG 元信息。返回结构化探针结果，不抛异常。"""
    if not sniff_is_png(data):
        return ImageProbe(
            is_png=False,
            width=0,
            height=0,
            has_alpha=False,
            has_transparent_pixel=False,
            readable=False,
            error="UNSUPPORTED_IMAGE_FORMAT",
        )

    try:
        with Image.open(io.BytesIO(data)) as image:
            image.load()
            width, height = image.size
            has_alpha = image.mode in {"RGBA", "LA", "PA"} or (
                "transparency" in image.info  # noqa: SIM118
            )
            has_transparent_pixel = False
            if has_alpha:
                alpha = image.getchannel("A") if "A" in image.getbands() else None
                if alpha is not None:
                    has_transparent_pixel = alpha.getextrema()[0] < 255
            return ImageProbe(
                is_png=True,
                width=width,
                height=height,
                has_alpha=has_alpha,
                has_transparent_pixel=has_transparent_pixel,
                readable=True,
            )
    except Exception as exc:  # noqa: BLE001 - 探针按契约返回，不中断调用
        return ImageProbe(
            is_png=True,
            width=0,
            height=0,
            has_alpha=False,
            has_transparent_pixel=False,
            readable=False,
            error=f"DECODE_FAILED: {exc}",
        )


def is_square(*, width: int, height: int) -> bool:
    return width > 0 and width == height


def meets_min_size(*, width: int, height: int, min_width: int, min_height: int) -> bool:
    return width >= min_width and height >= min_height
