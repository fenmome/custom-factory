"""生产保护（Guard）规则引擎与领取拦截测试。

覆盖审查发现的回归点：
- 必需角色"连续失败"语义（非连续计数）+ 首次出现非 FAIL 不崩溃（原 KeyError）
- 启动观察期（前 10 SKU：2 黄 / ≥3 红）
- RED-01/02/03 稳态阈值
- RED-05 系统异常连击（含类别切换清零）
- 最小影响范围暂停：PRODUCT_TYPE_SCOPE 暂停必须拦住该类型 SKU 领取（原缺陷：不传 scope）
- 试运行领取上限（trial_sku_limit）
- 试运行任一 FAIL → 回退 PAUSED
"""

from __future__ import annotations

from datetime import timedelta

import pytest
from sqlalchemy import select

from app.core.events import (
    GUARD_YELLOW,
    SYSTEM_EXCEPTION,
    record_event,
    utc_now,
)
from app.core.exceptions import ProductionPausedError
from app.models.guard import ProductionPauseControl, SkuGenerationClaim
from app.models.image import RevisionQA
from app.models.product import Batch, Product, ProductRevision
from app.services import production_guard_service, sku_generation_claim_service
from app.services.production_guard_service import (
    LEVEL_GREEN,
    LEVEL_RED,
    LEVEL_YELLOW,
    SCOPE_PRODUCT_TYPE,
    SCOPE_SYSTEM,
    ProductionGuardService,
)
from app.services.uuid_provider import new_uuid

WS = "33333333-3333-4333-8333-333333333333"


def _add_revision_qa(
    session,
    *,
    result: str = "PASS",
    role_state: str = "PASS",
    role: str = "main_image",
    minutes_offset: int = 0,
    revision_id: str | None = None,
) -> str:
    role_status = {role: {"state": role_state, "is_required": True}}
    rid = revision_id or new_uuid()
    session.add(
        RevisionQA(
            id=new_uuid(),
            workspace_id=WS,
            revision_id=rid,
            result=result,
            passed_count=0 if result == "FAIL" else 5,
            failed_count=1 if result == "FAIL" else 0,
            pending_count=0,
            required_role_status=role_status,
            qa_result_snapshot={},
            evaluated_at=utc_now() + timedelta(minutes=minutes_offset),
        )
    )
    session.flush()
    return rid


# ---------------- 必需角色连击 ----------------
def test_required_role_streak_resets_and_no_keyerror(session):
    """回归：旧实现 `streaks.setdefault(role, streaks[role])` 会在角色首次出现且
    非 FAIL 时抛 KeyError；且统计的是出现次数而非连续失败。"""
    # 最新行（offset 最大）非 FAIL，之前两行 FAIL → 连击应为 0
    _add_revision_qa(session, role_state="PASS", minutes_offset=30)
    _add_revision_qa(session, role_state="FAIL", minutes_offset=20)
    _add_revision_qa(session, role_state="FAIL", minutes_offset=10)

    streaks = ProductionGuardService()._required_role_streaks(session=session, workspace_id=WS, limit=50)
    assert streaks == {}

    evaluation = ProductionGuardService().evaluate(session=session, workspace_id=WS)
    assert evaluation.level == LEVEL_GREEN


def test_yellow03_and_red04_required_role_streaks(session):
    # 连续 2 个 FAIL → YELLOW-03
    _add_revision_qa(session, role_state="FAIL", minutes_offset=20)
    _add_revision_qa(session, role_state="FAIL", minutes_offset=10)
    evaluation = ProductionGuardService().evaluate(session=session, workspace_id=WS)
    assert evaluation.level == LEVEL_YELLOW
    assert evaluation.rule_id == "YELLOW-03"

    # 再加 1 个 FAIL（共连续 3 个）→ RED-04
    _add_revision_qa(session, role_state="FAIL", minutes_offset=5)
    evaluation = ProductionGuardService().evaluate(session=session, workspace_id=WS)
    assert evaluation.level == LEVEL_RED
    assert evaluation.rule_id == "RED-04"


# ---------------- 启动观察期 ----------------
def test_startup_observation_period(session):
    for i in range(2):
        _add_revision_qa(session, result="FAIL", role_state="FAIL", minutes_offset=10 - i)
    evaluation = ProductionGuardService().evaluate(session=session, workspace_id=WS)
    assert evaluation.level == LEVEL_YELLOW
    assert evaluation.rule_id == "STARTUP-YELLOW"

    for i in range(3):
        _add_revision_qa(session, result="FAIL", role_state="FAIL", minutes_offset=60 + i)
    evaluation = ProductionGuardService().evaluate(session=session, workspace_id=WS)
    assert evaluation.level == LEVEL_RED
    assert evaluation.rule_id == "STARTUP-RED"


def test_steady_state_yellow01_requires_full_window(session):
    """稳态 YELLOW-01 只在满 50 窗口时按失败率判定，避免小样本误报。"""
    for i in range(11):
        _add_revision_qa(session, result="FAIL" if i < 2 else "PASS", role_state="PASS", minutes_offset=i)
    evaluation = ProductionGuardService().evaluate(session=session, workspace_id=WS)
    assert evaluation.level == LEVEL_GREEN  # 11/50 样本，失败率 18% 但未满窗口


# ---------------- RED-05 系统异常连击 ----------------
def test_red05_exception_streak(session):
    for i in range(3):
        record_event(
            session,
            workspace_id=WS,
            entity_type="PRODUCTION",
            entity_id=WS,
            event_kind=SYSTEM_EXCEPTION,
            payload={"reason_code": "STORAGE_TIMEOUT"},
        )
    session.flush()
    evaluation = ProductionGuardService().evaluate(session=session, workspace_id=WS)
    assert evaluation.level == LEVEL_RED
    assert evaluation.rule_id == "RED-05"


def test_red05_exception_streak_broken_by_other_event(session):
    for i in range(2):
        record_event(
            session,
            workspace_id=WS,
            entity_type="PRODUCTION",
            entity_id=WS,
            event_kind=SYSTEM_EXCEPTION,
            payload={"reason_code": "STORAGE_TIMEOUT"},
        )
    record_event(
        session,
        workspace_id=WS,
        entity_type="PRODUCTION",
        entity_id=WS,
        event_kind=GUARD_YELLOW,
        payload={"rule": "YELLOW-02"},
    )
    session.flush()
    evaluation = ProductionGuardService().evaluate(session=session, workspace_id=WS)
    assert evaluation.level == LEVEL_GREEN


# ---------------- 领取拦截：scope / 试运行上限 ----------------
def _seed_claimable_batch(session, *, product_type_id: str, sku: str) -> str:
    """返回 revision_id。"""
    batch_id = new_uuid()
    session.add(
        Batch(
            id=batch_id,
            workspace_id=WS,
            product_type_id=product_type_id,
            requested_quantity=1,
            image_generation_route="CODEX",
            control_state="ACTIVE",
            request_key=f"rk-{batch_id}",
            input_snapshot_hash="0" * 64,
            usage_code="small_business_packaging",
            created_by_user_id=new_uuid(),
        )
    )
    product_id = new_uuid()
    session.add(
        Product(
            id=product_id,
            workspace_id=WS,
            batch_id=batch_id,
            sku_namespace=new_uuid(),
            internal_sku=sku,
            allocated_prefix="DZUVDTF",
            allocated_sequence=1,
        )
    )
    revision_id = new_uuid()
    session.add(
        ProductRevision(
            id=revision_id,
            workspace_id=WS,
            product_id=product_id,
            batch_id=batch_id,
            revision_number=1,
        )
    )
    session.flush()
    return revision_id


def test_product_type_pause_blocks_claim_of_that_type(session):
    revision_paused = _seed_claimable_batch(session, product_type_id="pt-paused", sku="SKU-A1")
    _seed_claimable_batch(session, product_type_id="pt-free", sku="SKU-B1")

    session.add(
        ProductionPauseControl(
            id=new_uuid(),
            workspace_id=WS,
            scope_kind=SCOPE_PRODUCT_TYPE,
            target={"product_type_id": "pt-paused"},
            state="PAUSED",
            trigger_rule_id="RED-01",
            rule_text="连续失败",
            reason="测试暂停",
            paused_at=utc_now(),
            updated_at=utc_now(),
            trial_sku_limit=3,
        )
    )
    session.flush()

    guard = ProductionGuardService()
    # 暂停范围内的候选被跳过（暂停范围外正常领取，FR-09）
    result = sku_generation_claim_service.claim(
        session=session,
        workspace_id=WS,
        executor_kind="CODEX",
        executor_id="exec-1",
        request_key="rq-1",
        batch_id=None,
    )
    assert result, "应领取到未暂停类型的 SKU"
    assert result["internal_sku"] == "SKU-B1"
    assert result["revision_id"] != revision_paused

    # 指定暂停类型批次领取 → 无可领取
    empty = sku_generation_claim_service.claim(
        session=session,
        workspace_id=WS,
        executor_kind="CODEX",
        executor_id="exec-2",
        request_key="rq-2",
        batch_id=None,
    )
    # 只剩 pt-paused 的候选 → 被跳过，返回空
    assert empty == {}


def test_system_pause_blocks_all_claims(session):
    _seed_claimable_batch(session, product_type_id="pt-1", sku="SKU-C1")
    session.add(
        ProductionPauseControl(
            id=new_uuid(),
            workspace_id=WS,
            scope_kind=SCOPE_SYSTEM,
            target={},
            state="PAUSED",
            trigger_rule_id="CRITICAL_STOP",
            rule_text="紧急停止",
            reason="测试",
            paused_at=utc_now(),
            updated_at=utc_now(),
            trial_sku_limit=3,
        )
    )
    session.flush()
    with pytest.raises(ProductionPausedError):
        sku_generation_claim_service.claim(
            session=session,
            workspace_id=WS,
            executor_kind="CODEX",
            executor_id="exec-1",
            request_key="rq-1",
            batch_id=None,
        )


def test_trial_claim_limit_enforced(session):
    revision_ids = [
        _seed_claimable_batch(session, product_type_id="pt-1", sku=f"SKU-T{i}") for i in range(4)
    ]
    trial = ProductionPauseControl(
        id=new_uuid(),
        workspace_id=WS,
        scope_kind=SCOPE_PRODUCT_TYPE,
        target={"product_type_id": "pt-1"},
        state="TRIAL_RUNNING",
        trigger_rule_id="RED-01",
        rule_text="连续失败",
        reason="试运行",
        paused_at=utc_now(),
        updated_at=utc_now(),
        trial_sku_limit=3,
    )
    session.add(trial)
    session.flush()

    for i in range(3):
        claimed = sku_generation_claim_service.claim(
            session=session,
            workspace_id=WS,
            executor_kind="CODEX",
            executor_id=f"exec-{i}",
            request_key=f"rq-{i}",
            batch_id=None,
        )
        assert claimed, f"第 {i + 1} 次领取应成功"

    # TRIAL_RUNNING 不阻断领取，但达到 trial_sku_limit 后不再发放（返回空）
    exhausted = sku_generation_claim_service.claim(
        session=session,
        workspace_id=WS,
        executor_kind="CODEX",
        executor_id="exec-x",
        request_key="rq-x",
        batch_id=None,
    )
    assert exhausted == {}
    assert int(trial.trial_claim_count) == 3


# ---------------- 试运行结果 ----------------
def test_trial_fail_returns_to_paused(session):
    control = ProductionPauseControl(
        id=new_uuid(),
        workspace_id=WS,
        scope_kind=SCOPE_SYSTEM,
        target={},
        state="TRIAL_RUNNING",
        trigger_rule_id="RED-02",
        rule_text="短窗失败",
        reason="测试",
        paused_at=utc_now(),
        updated_at=utc_now(),
        trial_sku_limit=3,
        trial_claim_count=1,
    )
    session.add(control)
    session.flush()

    ProductionGuardService().record_trial_result(
        session=session, workspace_id=WS, control_id=control.id, result="FAIL"
    )
    assert control.state == "PAUSED"

    ProductionGuardService().record_trial_result(
        session=session, workspace_id=WS, control_id=control.id, result="PASS"
    )
    assert control.state == "PAUSED"  # 重新计时，1/3 PASS 不足以解除

    control.trial_completed_count = 2
    ProductionGuardService().record_trial_result(
        session=session, workspace_id=WS, control_id=control.id, result="PASS"
    )
    assert control.state == "RESOLVED"
