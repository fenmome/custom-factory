"""载体对象解析器（FR-05 / agent.md 4.6）。

解析优先级：
1. Primary Query 的 ACTIVE 对象 → 直接使用
2. Primary Query 的对象非 ACTIVE → **HOLD**（不替换！）
3. Primary 无对象 → Secondary Query 中第一个 ACTIVE
4. 全部无对象 → 固定字母序 GIFT_BOX → MAILER_BOX → PACKAGING_BOX → PRODUCT_BOX

所有对象均需满足表面条件：clean, dry, smooth, hard, non_porous, external_surface
"""

from __future__ import annotations

from dataclasses import dataclass

from app.core.exceptions import ValidationError
from app.core.resource_loader import Resource, allowed_objects, product_profile


@dataclass(frozen=True)
class ObjectResolution:
    object: str
    source: str  # PRIMARY_ACTIVE | SECONDARY_ACTIVE | FIXED_ORDER_FALLBACK
    surface_gate: list[str]
    surface_requirements: dict[str, list[str]]


class ObjectHoldError(ValidationError):
    code = 40020
    default_message = "Primary Query 的对象处于非 ACTIVE 状态，必须 HOLD，禁止替换"


class ObjectResolver:
    def __init__(
        self,
        *,
        object_rule: Resource | None = None,
        profile: Resource | None = None,
    ) -> None:
        self.object_rule = object_rule or allowed_objects()
        self.profile = profile or product_profile()

    @property
    def _active(self) -> list[str]:
        return list(self.object_rule["active_objects"])

    @property
    def _hold(self) -> set[str]:
        return set(self.object_rule["hold_objects"])

    @property
    def _cross_usage(self) -> set[str]:
        return set(self.object_rule["cross_usage_only"])

    @property
    def _fixed_order(self) -> list[str]:
        return list(self.object_rule["fixed_order"])

    def status_of(self, obj: str) -> str:
        if obj in self._active:
            return "ACTIVE"
        if obj in self._hold:
            return "HOLD"
        if obj in self._cross_usage:
            return "CROSS_USAGE_ONLY"
        return "UNKNOWN"

    def surface_requirements_for(self, obj: str) -> dict[str, list[str]]:
        requirements: dict[str, list[str]] = {}
        spec = self.object_rule.get("object_surface_requirements", {}).get(obj)
        if spec:
            if spec.get("finish"):
                requirements["finish"] = list(spec["finish"])
            if spec.get("forbidden"):
                requirements["forbidden"] = list(spec["forbidden"])
        return requirements

    def resolve(
        self,
        *,
        primary_objects: list[str] | None = None,
        secondary_objects: list[str] | None = None,
        allow_fallback: bool = True,
    ) -> ObjectResolution:
        primary = [o for o in (primary_objects or []) if o]
        secondary = [o for o in (secondary_objects or []) if o]

        surface_gate = list(self.profile["surface_gate"])

        # 1) Primary 有对象
        if primary:
            for obj in primary:
                status = self.status_of(obj)
                if status == "ACTIVE":
                    return ObjectResolution(
                        object=obj,
                        source="PRIMARY_ACTIVE",
                        surface_gate=surface_gate,
                        surface_requirements=self.surface_requirements_for(obj),
                    )
            # 2) Primary 有对象但全部非 ACTIVE → HOLD
            raise ObjectHoldError(
                detail=f"Primary 对象 {primary} 均非 ACTIVE（状态={[self.status_of(o) for o in primary]}）"
            )

        # 3) Primary 无对象 → Secondary 第一个 ACTIVE
        for obj in secondary:
            if self.status_of(obj) == "ACTIVE":
                return ObjectResolution(
                    object=obj,
                    source="SECONDARY_ACTIVE",
                    surface_gate=surface_gate,
                    surface_requirements=self.surface_requirements_for(obj),
                )

        # 4) 固定字母序兜底
        if not allow_fallback:
            raise ObjectHoldError(detail="无可用对象且未允许兜底")
        fallback = self._fixed_order[0] if self._fixed_order else "PRODUCT_BOX"
        return ObjectResolution(
            object=fallback,
            source="FIXED_ORDER_FALLBACK",
            surface_gate=surface_gate,
            surface_requirements=self.surface_requirements_for(fallback),
        )
