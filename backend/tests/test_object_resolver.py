"""对象解析优先级测试（FR-05）。"""

from __future__ import annotations

import pytest

from app.services.object_resolver import ObjectHoldError, ObjectResolver


@pytest.fixture()
def resolver() -> ObjectResolver:
    return ObjectResolver()


def test_primary_active_wins(resolver):
    result = resolver.resolve(primary_objects=["PACKAGING_BOX", "GIFT_BOX"])
    assert result.object == "PACKAGING_BOX"
    assert result.source == "PRIMARY_ACTIVE"


def test_primary_non_active_holds_instead_of_substituting(resolver):
    with pytest.raises(ObjectHoldError):
        resolver.resolve(primary_objects=["SHIPPING_BOX"])


def test_secondary_used_when_primary_has_no_object(resolver):
    result = resolver.resolve(primary_objects=[], secondary_objects=["JEWELRY_PACKAGING", "GIFT_BOX"])
    assert result.object == "GIFT_BOX"
    assert result.source == "SECONDARY_ACTIVE"


def test_fixed_order_fallback_when_nothing_available(resolver):
    result = resolver.resolve(primary_objects=[], secondary_objects=[])
    assert result.object == "GIFT_BOX"
    assert result.source == "FIXED_ORDER_FALLBACK"


def test_surface_gate_always_attached(resolver):
    result = resolver.resolve(primary_objects=["MAILER_BOX"])
    assert result.surface_gate == ["clean", "dry", "smooth", "hard", "non_porous", "external_surface"]
    assert "finish" in result.surface_requirements


def test_cross_usage_objects_are_not_active(resolver):
    assert resolver.status_of("BOTTLE") == "CROSS_USAGE_ONLY"
