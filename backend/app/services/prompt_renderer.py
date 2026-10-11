"""UV DTF 八槽位提示词渲染器。

FR-06：输入白名单 = PrimaryVisualSemantic + 解析后的冻结对象 + sold_entity
       + 表面条件 + 冻结的艺术品事实（品牌/logo/配色/风格）。
渲染结果 = shared_base（10 条）+ 视觉计划 + 槽位专属指令 + 可见文字白名单。
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import ValidationError
from app.core.hashing import sha256_hex
from app.core.resource_loader import Resource, image_policy, product_profile, prompt_rule, visual_preparation


@dataclass(frozen=True)
class FrozenArtworkFacts:
    """冻结的艺术品事实（同 SKU 内 8 槽位保持一致）。"""

    brand_name: str
    style: str
    palette: list[str]
    logo_motif: str
    surface_gate: list[str]


@dataclass(frozen=True)
class RenderedSlotPrompt:
    slot: int
    role: str
    is_required: bool
    prompt: str
    text_whitelist: list[str]
    reference_policy: str
    prompt_hash: str


class PromptRenderer:
    def __init__(
        self,
        *,
        rule: Resource | None = None,
        policy: Resource | None = None,
        prep: Resource | None = None,
        profile: Resource | None = None,
    ) -> None:
        self.rule = rule or prompt_rule()
        self.policy = policy or image_policy()
        self.prep = prep or visual_preparation()
        self.profile = profile or product_profile()

    # ---------------- 前置校验 ----------------
    def _require(self, role: str) -> bool:
        for entry in self.policy["slot_roles"]:
            if entry["role"] == role:
                return bool(entry["is_required"])
        raise ValidationError(detail=f"策略中不存在角色 {role}")

    def resolve_style(self, style_code: str | None) -> str:
        if not style_code:
            return "clean marketplace e-commerce"
        for item in self.prep["styles"]:
            if item["code"] == style_code:
                return item["code"]
        raise ValidationError(detail=f"无效的视觉风格: {style_code}")

    def resolve_palette(self, palette_code: str | None) -> list[str]:
        if not palette_code:
            return self.prep["palettes"][0]["colors"]
        for item in self.prep["palettes"]:
            if item["code"] == palette_code:
                return list(item["colors"])
        raise ValidationError(detail=f"无效的配色方案: {palette_code}")

    # ---------------- 渲染 ----------------
    def render(
        self,
        *,
        semantic: dict,
        resolved_object: str,
        facts: FrozenArtworkFacts,
        presentation_variant: dict | None = None,
    ) -> list[RenderedSlotPrompt]:
        shared = list(self.rule["shared_base"])
        objective = self._build_objective_block(
            sold_entity=self.profile.get("sold_entity"),
            resolved_object=resolved_object,
            semantic=semantic,
            facts=facts,
        )

        rendered: list[RenderedSlotPrompt] = []
        for slot in self.rule["slots"]:
            block = self._build_slot_block(
                slot=slot,
                shared=shared,
                objective=objective,
                facts=facts,
                presentation_variant=presentation_variant,
            )
            rendered.append(
                RenderedSlotPrompt(
                    slot=int(slot["slot"]),
                    role=str(slot["role"]),
                    is_required=bool(slot["is_required"]),
                    prompt=block,
                    text_whitelist=[str(t) for t in slot["text_whitelist"]],
                    reference_policy=str(slot["reference_policy"]),
                    prompt_hash=sha256_hex(block),
                )
            )
        return rendered

    def _build_objective_block(
        self,
        *,
        sold_entity: str | None,
        resolved_object: str,
        semantic: dict,
        facts: FrozenArtworkFacts,
    ) -> str:
        lines = [
            "[OBJECTIVE]",
            f"Sold entity: {sold_entity or 'Custom UV DTF transfer / decal'}",
            f"Resolved primary object (carrier, not sold): {resolved_object}",
            f"Use case: {semantic.get('use_case', 'small_business_packaging')}",
            f"Surface conditions: {', '.join(facts.surface_gate)}",
            "Primary Query meaning is the ONLY semantic input; there is no secondary semantic input.",
            "",
            "[FROZEN ARTWORK FACTS]",
            f"Brand name (frozen spelling, never alter): {facts.brand_name}",
            f"Logo motif: {facts.logo_motif}",
            f"Style: {facts.style}",
            f"Palette: {', '.join(facts.palette)}",
        ]
        return "\n".join(lines)

    def _build_slot_block(
        self,
        *,
        slot: dict,
        shared: list[str],
        objective: str,
        facts: FrozenArtworkFacts,
        presentation_variant: dict | None,
    ) -> str:
        whitelist = [str(t) for t in slot["text_whitelist"]]
        allowed = list(whitelist) + [facts.brand_name]
        allowed_block = "\n".join(f"  - {item}" for item in allowed) if allowed else "  (none)"

        parts: list[str] = [objective, "", f"[SLOT {int(slot['slot']):02d} — {slot['role']}]", slot["instruction"]]

        if presentation_variant:
            parts.append("")
            parts.append("[PRESENTATION VARIANT — overrides general camera/layout only]")
            for key in ("scene", "background", "camera", "carrier_finish", "props"):
                if presentation_variant.get(key):
                    parts.append(f"  {key}: {presentation_variant[key]}")

        parts.append("")
        parts.append("[ALLOWED VISIBLE TEXT — anything beyond this list is forbidden]")
        parts.append(allowed_block)

        parts.append("")
        parts.append("[SHARED BASE RULES]")
        for index, rule_text in enumerate(shared, start=1):
            parts.append(f"{index}. {rule_text}")

        return "\n".join(parts)

    def forbidden_text(self) -> list[str]:
        return list(self.rule["forbidden_text"])
