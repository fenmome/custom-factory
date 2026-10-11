"""SKU 分配规则测试。"""

from __future__ import annotations

import pytest

from app.core.exceptions import SkuPrefixConflictError, SkuSequenceWidthTooSmallError
from app.services import sku_service
from app.services.uuid_provider import new_uuid


def test_format_sku_pads_sequence(session, workspace_id):
    assert sku_service.format_sku(prefix="DZUVDTF", sequence=1, width=6) == "DZUVDTF000001"
    assert sku_service.format_sku(prefix="DZUVDTF", sequence=123456, width=6) == "DZUVDTF123456"


def test_sequence_starts_at_one(session, workspace_id):
    with pytest.raises(Exception):
        sku_service.format_sku(prefix="AB", sequence=0, width=6)


def test_allocate_block_is_contiguous(session, workspace_id):
    config = sku_service.create_config(
        session=session,
        workspace_id=workspace_id,
        product_type_code="UV_DTF",
        display_name="定制水晶标",
        prefix="DZUVDTF",
        sequence_width=6,
    )
    block = sku_service.allocate_sequence_block(session=session, config=config, quantity=10)
    assert [b[1] for b in block] == list(range(1, 11))
    assert block[0][0] == "DZUVDTF000001"
    assert block[9][0] == "DZUVDTF000010"
    assert config.last_sequence == 10


def test_prefix_is_globally_unique(session, workspace_id):
    sku_service.create_config(
        session=session,
        workspace_id=workspace_id,
        product_type_code="UV_DTF",
        display_name="定制水晶标",
        prefix="DZUVDTF",
    )
    session.flush()
    with pytest.raises(SkuPrefixConflictError):
        sku_service.create_config(
            session=session,
            workspace_id=workspace_id,
            product_type_code="OTHER",
            display_name="其它",
            prefix="DZUVDTF",
        )


def test_sequence_width_cannot_shrink_below_current(session, workspace_id):
    config = sku_service.create_config(
        session=session,
        workspace_id=workspace_id,
        product_type_code="UV_DTF2",
        display_name="测试",
        prefix="ZZ",
        sequence_width=6,
    )
    sku_service.allocate_sequence_block(session=session, config=config, quantity=123456)
    with pytest.raises(SkuSequenceWidthTooSmallError):
        sku_service.update_config(session=session, config=config, sequence_width=2)


def test_prefix_validation(session, workspace_id):
    assert sku_service.validate_prefix("abc123") == "ABC123"
    with pytest.raises(Exception):
        sku_service.validate_prefix("bad-prefix!")


def test_new_uuid_is_v4_string():
    value = new_uuid()
    assert len(value) == 36
    assert value[14] == "4"
