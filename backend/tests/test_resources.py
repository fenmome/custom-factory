"""业务资源加载与内容寻址测试。"""

from __future__ import annotations

from app.core.hashing import canonical_json_bytes, sha256_hex
from app.core.resource_loader import (
    allowed_objects,
    attribute_schema,
    guard_rules,
    image_policy,
    iter_manifest,
    product_profile,
    prompt_rule,
    visual_preparation,
)


def test_all_resources_load_with_hash():
    for resource in (
        prompt_rule(),
        image_policy(),
        allowed_objects(),
        visual_preparation(),
        guard_rules(),
        product_profile(),
        attribute_schema(),
    ):
        assert resource.content_hash
        assert len(resource.content_hash) == 64
        assert resource.version


def test_prompt_rule_has_eight_slots():
    slots = prompt_rule()["slots"]
    assert len(slots) == 8
    assert [s["slot"] for s in slots] == [1, 2, 3, 4, 5, 6, 7, 8]


def test_prompt_rule_shared_base_has_ten_rules():
    assert len(prompt_rule()["shared_base"]) == 10


def test_image_policy_matches_prompt_slots():
    policy_roles = image_policy()["slot_roles"]
    prompt_slots = prompt_rule()["slots"]
    assert len(policy_roles) == len(prompt_slots)
    for policy_slot, prompt_slot in zip(policy_roles, prompt_slots, strict=True):
        assert policy_slot["role"] == prompt_slot["role"]


def test_policy_requires_five_images_min():
    assert image_policy()["min_ready_count"] == 5
    assert int(image_policy()["planned_count"]) == 8


def test_surface_gate_comes_from_profile():
    gate = product_profile()["surface_gate"]
    assert gate == ["clean", "dry", "smooth", "hard", "non_porous", "external_surface"]
    assert attribute_schema()["properties"]["surface_gate"]["const"] == gate


def test_guard_thresholds_present():
    rules = guard_rules().data
    assert rules["red_consecutive_skus"] == 5
    assert rules["sku_yellow_min_percent"] == 10
    assert rules["image_yellow_min_percent"] == 20
    assert rules["trial_sku_limit"] == 3


def test_canonical_json_is_stable():
    payload_a = {"b": 1, "a": [1, 2, {"z": "z", "y": "y"}]}
    payload_b = {"a": [1, 2, {"y": "y", "z": "z"}], "b": 1}
    assert sha256_hex(payload_a) == sha256_hex(payload_b)
    assert canonical_json_bytes(payload_a) == canonical_json_bytes(payload_b)


def test_manifest_covers_every_resource():
    entries = iter_manifest()
    paths = {e["path"] for e in entries}
    assert "prompt_rules/UV_DTF_PROMPT_RULE_V1_4.json" in paths
    assert "image_policy/uv_dtf_image_policy_v1_2.json" in paths
    assert len(entries) >= 7
