"""Primary Query 视觉语义提取。

FR-06 输入白名单：PrimaryVisualSemantic（**仅** Primary Query 的结构化语义）。
禁止输入：Secondary Query 文本、完整标题、买家联系方式。
"""

from __future__ import annotations

from dataclasses import dataclass, field

from app.core.exceptions import ValidationError
from app.core.resource_loader import Resource, allowed_objects

# 从 Query 文本里识别的对象关键词表（键必须与 allowed_objects 中的对象一致）
OBJECT_KEYWORDS: dict[str, tuple[str, ...]] = {
    "GIFT_BOX": ("gift box", "gift-box", "giftbox"),
    "MAILER_BOX": ("mailer box", "mailer-box", "mailerbox", "shipping mailer"),
    "PACKAGING_BOX": ("packaging box", "packaging-box", "package box", "small box"),
    "PRODUCT_BOX": ("product box", "product-box", "retail box", "brand box"),
    "SHIPPING_BOX": ("shipping box", "carton"),
    "RETAIL_BOX": ("retail box", "shelf box"),
    "RIGID_BOX": ("rigid box", "set-up box"),
    "COATED_BOX": ("coated box", "coated mailer"),
    "JEWELRY_PACKAGING": ("jewelry box", "jewellery packaging"),
    "TIN_CONTAINER": ("tin", "tin container"),
    "BOTTLE": ("bottle",),
    "JAR": ("jar",),
    "CANDLE_JAR": ("candle jar",),
    "COSMETIC_CONTAINER": ("cosmetic", "cream jar"),
    "CUP_TUMBLER": ("tumbler", "cup"),
}

FORBIDDEN_INPUT_MARKERS = ("@", "http://", "https://", "phone:", "email:")


@dataclass(frozen=True)
class PrimaryVisualSemantic:
    """结构化视觉语义（进入 Prompt 渲染的唯一语义来源）。"""

    query_id: str
    query_text: str
    use_case: str
    objects: list[str] = field(default_factory=list)
    motif_candidates: list[str] = field(default_factory=list)

    def payload(self) -> dict:
        return {
            "query_id": self.query_id,
            "query_text": self.query_text,
            "use_case": self.use_case,
            "objects": list(self.objects),
            "motif_candidates": list(self.motif_candidates),
        }


class PrimaryVisualSemanticService:
    """把 Primary Query 文本规约为结构化语义。"""

    def __init__(self, *, object_rule: Resource | None = None) -> None:
        self.object_rule = object_rule or allowed_objects()

    def extract(
        self,
        *,
        query_id: str,
        query_text: str,
        use_case: str,
        motif_candidates: list[str] | None = None,
    ) -> PrimaryVisualSemantic:
        normalized = self._sanitize(query_text)
        return PrimaryVisualSemantic(
            query_id=query_id,
            query_text=normalized,
            use_case=use_case,
            objects=self._detect_objects(normalized),
            motif_candidates=list(motif_candidates or []),
        )

    @staticmethod
    def _sanitize(text: str) -> str:
        lowered = " ".join(text.split()).lower()
        for marker in FORBIDDEN_INPUT_MARKERS:
            if marker in lowered:
                raise ValidationError(detail="Query 文本中不允许包含联系方式/链接等禁止输入")
        return " ".join(text.split())

    @staticmethod
    def _detect_objects(normalized: str) -> list[str]:
        lowered = normalized.lower()
        hits: list[str] = []
        for obj, keywords in OBJECT_KEYWORDS.items():
            if any(keyword in lowered for keyword in keywords):
                hits.append(obj)
        # 保持确定性：按对象名排序，避免命中顺序影响结果
        return sorted(set(hits))
