"""生产保护（FR-09 / agent.md 4.4）。

三色状态：
- GREEN 正常
- YELLOW 警告（不降速、不停止）
- RED 暂停（暂停范围内停止新领取，已开始的可安全结束）
- CRITICAL_STOP 紧急停止（认证失败/配额耗尽/存储故障）

暂停范围取最小影响：PRODUCT_TYPE_SCOPE / PROVIDER_MODEL_SCOPE / SYSTEM_SCOPE
恢复：PAUSED → 人工开始试运行(≤3 SKU) → 3/3 PASS → RESOLVED；任一 FAIL → 回退 PAUSED
"""

from __future__ import annotations

from collections.abc import Sequence
from dataclasses import dataclass

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.events import (
    GUARD_PAUSED,
    GUARD_RESOLVED,
    GUARD_TRIAL_EVALUATED,
    GUARD_TRIAL_STARTED,
    GUARD_YELLOW,
    SYSTEM_EXCEPTION,
    record_event,
    utc_now,
)
from app.models.audit import LifecycleEvent
from app.core.exceptions import AppError, TrialRunNotAllowedError
from app.core.resource_loader import Resource, guard_rules
from app.models.guard import ProductionPauseControl
from app.models.image import ImageQA, RevisionQA
from app.models.product import ProductRevision
from app.services.uuid_provider import new_uuid

LEVEL_GREEN = "GREEN"
LEVEL_YELLOW = "YELLOW"
LEVEL_RED = "RED"
LEVEL_CRITICAL = "CRITICAL_STOP"

SCOPE_PRODUCT_TYPE = "PRODUCT_TYPE_SCOPE"
SCOPE_PROVIDER_MODEL = "PROVIDER_MODEL_SCOPE"
SCOPE_SYSTEM = "SYSTEM_SCOPE"


@dataclass(frozen=True)
class GuardEvaluation:
    level: str
    rule_id: str | None
    reason: str | None
    metrics: dict


class GuardScopeTooSmall(AppError):
    code = 41403
    default_message = "无法确定暂停范围"


class ProductionGuardService:
    def __init__(self, *, rules: Resource | None = None) -> None:
        self.rules = rules or guard_rules()

    # ---------------- 窗口统计 ----------------
    def _recent_revision_results(self, *, session: Session, workspace_id: str, limit: int) -> list[str]:
        rows = session.scalars(
            select(RevisionQA.result)
            .where(RevisionQA.workspace_id == workspace_id)
            .order_by(RevisionQA.evaluated_at.desc())
            .limit(limit)
        ).all()
        return [str(r) for r in rows]

    def _recent_image_fail_rate(self, *, session: Session, workspace_id: str, limit: int) -> tuple[int, int]:
        window = int(self.rules["image_window"])
        rows = session.scalars(
            select(ImageQA.result)
            .where(ImageQA.workspace_id == workspace_id, ImageQA.kind.in_(["TECHNICAL", "SEMANTIC"]))
            .order_by(ImageQA.evaluated_at.desc())
            .limit(min(limit, window))
        ).all()
        total = len(rows)
        failed = sum(1 for r in rows if str(r) == "FAIL")
        return failed, total

    def _required_role_streaks(self, *, session: Session, workspace_id: str, limit: int) -> dict[str, int]:
        """按"连续 N 个 SKU 失败"语义统计必需角色失败连击。

        行按时间倒序（最新在前）；某行中角色为 FAIL 则连击 +1，
        该行中角色存在但未 FAIL 则连击清零；该行未出现该角色（如不同产品类型
        角色集不同）则不影响其连击。
        """
        rows: Sequence[RevisionQA] = session.scalars(
            select(RevisionQA)
            .where(RevisionQA.workspace_id == workspace_id)
            .order_by(RevisionQA.evaluated_at.desc())
            .limit(limit)
        ).all()

        streaks: dict[str, int] = {}
        closed: set[str] = set()
        for row in rows:
            status = row.required_role_status or {}
            for role, info in status.items():
                if not isinstance(info, dict) or not info.get("is_required"):
                    continue
                if role in closed:
                    continue  # 从最新往回遇到非 FAIL 即封口，更早的失败不属于当前连击
                if info.get("state") == "FAIL":
                    streaks[role] = streaks.get(role, 0) + 1
                else:
                    closed.add(role)
        return {role: count for role, count in streaks.items() if count > 0}

    def _exception_streak(self, *, session: Session, workspace_id: str, limit: int = 30) -> int:
        """RED-05：最近连续上报的同类系统异常次数（被其他 PRODUCTION 事件打断即清零）。"""
        events = session.scalars(
            select(LifecycleEvent)
            .where(LifecycleEvent.workspace_id == workspace_id, LifecycleEvent.entity_type == "PRODUCTION")
            .order_by(LifecycleEvent.occurred_at.desc(), LifecycleEvent.id.desc())
            .limit(limit)
        ).all()

        streak = 0
        reason_code: str | None = None
        for event in events:
            if event.event_kind != SYSTEM_EXCEPTION:
                break
            code = (event.payload or {}).get("reason_code")
            if reason_code is not None and code != reason_code:
                break  # 异常类别变化：不同异常不叠加连击
            reason_code = code
            streak += 1
        return streak

    # ---------------- 评估 ----------------
    def evaluate(self, *, session: Session, workspace_id: str, product_type_id: str | None = None) -> GuardEvaluation:
        rules = self.rules.data
        sku_window = int(rules["sku_window"])
        startup_skus = int(rules["startup_skus"])
        results = self._recent_revision_results(session=session, workspace_id=workspace_id, limit=sku_window)
        total = len(results)
        failed = sum(1 for r in results if r == "FAIL")

        metrics: dict = {"sku_window_total": total, "sku_window_failed": failed}

        # 启动观察期（FR-09：前 N 个 SKU：0-1 继续 / 2 黄 / ≥3 红）
        if total <= startup_skus:
            metrics["startup_phase"] = True
            if failed >= int(rules["startup_red_failures"]):
                return GuardEvaluation(
                    LEVEL_RED, "STARTUP-RED", f"启动期 {total} 个 SKU 中 {failed} 个失败（阈值 {rules['startup_red_failures']}）", metrics
                )
            if failed >= int(rules["startup_yellow_failures"]):
                return GuardEvaluation(
                    LEVEL_YELLOW, "STARTUP-YELLOW", f"启动期 {total} 个 SKU 中 {failed} 个失败（阈值 {rules['startup_yellow_failures']}）", metrics
                )

        # 必需角色连击：先判 RED-04 再判 YELLOW-03
        streaks = self._required_role_streaks(session=session, workspace_id=workspace_id, limit=sku_window)
        if streaks:
            metrics["required_role_streaks"] = streaks
        r_streak = int(rules["red_required_role_streak"])
        y_streak = int(rules["yellow_required_role_streak"])
        for role, count in streaks.items():
            if count >= r_streak:
                return GuardEvaluation(LEVEL_RED, "RED-04", f"必需角色 {role} 连续 {count} 个 SKU 失败", metrics)
        for role, count in streaks.items():
            if count >= y_streak:
                return GuardEvaluation(LEVEL_YELLOW, "YELLOW-03", f"必需角色 {role} 连续 {count} 个 SKU 失败", metrics)

        # RED-01: 连续 5 个 SKU 未 READY（从最新往前数，遇 PASS 截断）
        consecutive = 0
        for result in results:
            if result == "PASS":
                break
            consecutive += 1
        metrics["consecutive_not_ready"] = consecutive
        if consecutive >= int(rules["red_consecutive_skus"]):
            return GuardEvaluation(LEVEL_RED, "RED-01", f"连续 {consecutive} 个 SKU 未通过 READY", metrics)

        # RED-02: 最近 20 中 ≥6 失败
        short = min(int(rules["red_short_window"]), total)
        short_failed = sum(1 for r in results[:short] if r == "FAIL")
        metrics["short_window_failed"] = short_failed
        if short >= int(rules["red_short_window"]) and short_failed >= int(rules["red_short_failures"]):
            return GuardEvaluation(LEVEL_RED, "RED-02", f"最近 {short} 个 SKU 中 {short_failed} 个失败", metrics)

        # RED-03: 50 中 ≥10 失败（窗口未满时不触发）
        if total >= sku_window and failed >= int(rules["red_long_failures"]):
            return GuardEvaluation(LEVEL_RED, "RED-03", f"最近 {total} 个 SKU 中 {failed} 个失败", metrics)

        # YELLOW-01: 稳态 50 SKU 失败率 10%~20%（仅统计满窗口，避免小样本误报）
        if total >= sku_window:
            rate = (failed / total * 100) if total else 0.0
            metrics["sku_fail_rate_percent"] = round(rate, 2)
            if int(rules["sku_yellow_min_percent"]) <= rate < int(rules["sku_yellow_max_percent"]):
                return GuardEvaluation(LEVEL_YELLOW, "YELLOW-01", f"最近 {total} 个 SKU 失败率 {rate:.1f}%", metrics)

        # YELLOW-02: 100 图失败率 ≥20%
        img_failed, img_total = self._recent_image_fail_rate(
            session=session, workspace_id=workspace_id, limit=int(rules["image_window"])
        )
        metrics["image_window_total"] = img_total
        metrics["image_window_failed"] = img_failed
        if img_total >= int(rules["image_window"]) and img_failed:
            img_rate = img_failed / img_total * 100
            metrics["image_fail_rate_percent"] = round(img_rate, 2)
            if img_rate >= int(rules["image_yellow_min_percent"]):
                return GuardEvaluation(LEVEL_YELLOW, "YELLOW-02", f"最近 {img_total} 张图失败率 {img_rate:.1f}%", metrics)

        # RED-05: 同一非致命系统异常连续 ≥3 次（无上报即恒为 0）
        exception_streak = self._exception_streak(session=session, workspace_id=workspace_id)
        metrics["exception_streak"] = exception_streak
        if exception_streak >= int(rules["red_exception_streak"]):
            return GuardEvaluation(LEVEL_RED, "RED-05", f"同一系统异常连续上报 {exception_streak} 次", metrics)

        return GuardEvaluation(LEVEL_GREEN, None, None, metrics)

    # ---------------- 暂停 ----------------
    def pause(
        self,
        *,
        session: Session,
        workspace_id: str,
        scope_kind: str,
        target: dict,
        trigger_rule_id: str,
        rule_text: str,
        reason: str,
    ) -> ProductionPauseControl:
        existing = self.active_pause(session=session, workspace_id=workspace_id, scope_kind=scope_kind, target=target)
        if existing is not None:
            return existing

        control = ProductionPauseControl(
            id=new_uuid(),
            workspace_id=workspace_id,
            scope_kind=scope_kind,
            target=target,
            state="PAUSED",
            trigger_rule_id=trigger_rule_id,
            rule_text=rule_text,
            reason=reason,
            paused_at=utc_now(),
            updated_at=utc_now(),
            trial_sku_limit=int(self.rules["trial_sku_limit"]),
        )
        session.add(control)
        session.flush()
        record_event(
            session,
            workspace_id=workspace_id,
            entity_type="PRODUCTION",
            entity_id=control.id,
            event_kind=GUARD_PAUSED,
            payload={"scope_kind": scope_kind, "target": target, "rule": trigger_rule_id},
        )
        session.flush()
        return control

    def critical_stop(
        self,
        *,
        session: Session,
        workspace_id: str,
        reason: str,
    ) -> ProductionPauseControl:
        return self.pause(
            session=session,
            workspace_id=workspace_id,
            scope_kind=SCOPE_SYSTEM,
            target={},
            trigger_rule_id="CRITICAL_STOP",
            rule_text="认证失败 / 配额耗尽 / 存储故障等致命异常，立即停止",
            reason=reason,
        )

    def evaluate_and_apply(
        self,
        *,
        session: Session,
        workspace_id: str,
        product_type_id: str | None = None,
        provider_model: str | None = None,
    ) -> GuardEvaluation:
        """评估并按最小影响范围自动暂停（YELLOW 只告警不暂停）。"""
        evaluation = self.evaluate(session=session, workspace_id=workspace_id, product_type_id=product_type_id)

        if evaluation.level == LEVEL_YELLOW:
            record_event(
                session,
                workspace_id=workspace_id,
                entity_type="PRODUCTION",
                entity_id=workspace_id,
                event_kind=GUARD_YELLOW,
                payload={"rule": evaluation.rule_id, "reason": evaluation.reason, "metrics": evaluation.metrics},
            )
            session.flush()
            return evaluation

        if evaluation.level != LEVEL_RED or evaluation.rule_id is None:
            return evaluation

        # 最小影响范围：PAUSED 优先取最窄作用域
        scope_kind, target = self._minimal_scope(product_type_id=product_type_id, provider_model=provider_model)
        self.pause(
            session=session,
            workspace_id=workspace_id,
            scope_kind=scope_kind,
            target=target,
            trigger_rule_id=evaluation.rule_id,
            rule_text=evaluation.reason or "",
            reason=evaluation.reason or "",
        )
        return evaluation

    @staticmethod
    def _minimal_scope(*, product_type_id: str | None, provider_model: str | None) -> tuple[str, dict]:
        if product_type_id:
            return SCOPE_PRODUCT_TYPE, {"product_type_id": product_type_id}
        if provider_model:
            return SCOPE_PROVIDER_MODEL, {"provider_model": provider_model}
        return SCOPE_SYSTEM, {}

    # ---------------- 查询 ----------------
    @staticmethod
    def active_pauses(*, session: Session, workspace_id: str) -> Sequence[ProductionPauseControl]:
        return session.scalars(
            select(ProductionPauseControl)
            .where(
                ProductionPauseControl.workspace_id == workspace_id,
                ProductionPauseControl.state.in_(["PAUSED", "TRIAL_RUNNING"]),
            )
            .order_by(ProductionPauseControl.paused_at.desc())
        ).all()

    @staticmethod
    def active_pause(
        *, session: Session, workspace_id: str, scope_kind: str, target: dict
    ) -> ProductionPauseControl | None:
        rows = ProductionGuardService.active_pauses(session=session, workspace_id=workspace_id)
        for row in rows:
            if row.scope_kind == scope_kind and row.target == target:
                return row
        return None

    def is_paused(
        self,
        *,
        session: Session,
        workspace_id: str,
        product_type_id: str | None = None,
        provider_model: str | None = None,
    ) -> ProductionPauseControl | None:
        """领取前检查：命中任一作用域即暂停。"""
        pauses = self.active_pauses(session=session, workspace_id=workspace_id)
        system = next((p for p in pauses if p.scope_kind == SCOPE_SYSTEM), None)
        if system is not None and system.state == "PAUSED":
            return system
        if product_type_id:
            hit = next(
                (
                    p
                    for p in pauses
                    if p.scope_kind == SCOPE_PRODUCT_TYPE
                    and p.target.get("product_type_id") == product_type_id
                    and p.state == "PAUSED"
                ),
                None,
            )
            if hit is not None:
                return hit
        if provider_model:
            hit = next(
                (
                    p
                    for p in pauses
                    if p.scope_kind == SCOPE_PROVIDER_MODEL
                    and p.target.get("provider_model") == provider_model
                    and p.state == "PAUSED"
                ),
                None,
            )
            if hit is not None:
                return hit
        return system if system is not None and system.state == "PAUSED" else None

    # ---------------- 试运行恢复 ----------------
    def start_trial(self, *, session: Session, workspace_id: str, control_id: str) -> ProductionPauseControl:
        control = session.scalar(
            select(ProductionPauseControl).where(
                ProductionPauseControl.workspace_id == workspace_id,
                ProductionPauseControl.id == control_id,
            )
        )
        if control is None:
            raise TrialRunNotAllowedError(detail="暂停控制不存在")
        if control.state != "PAUSED":
            raise TrialRunNotAllowedError(detail=f"当前状态 {control.state} 不可开始试运行")

        control.state = "TRIAL_RUNNING"
        control.trial_claim_count = 0
        control.trial_completed_count = 0
        control.trial_pass_count = 0
        control.trial_fail_count = 0
        control.trial_sku_limit = int(self.rules["trial_sku_limit"])
        control.updated_at = utc_now()
        session.flush()

        record_event(
            session,
            workspace_id=workspace_id,
            entity_type="PRODUCTION",
            entity_id=control.id,
            event_kind=GUARD_TRIAL_STARTED,
            payload={"limit": control.trial_sku_limit},
        )
        session.flush()
        return control

    def record_trial_result(
        self,
        *,
        session: Session,
        workspace_id: str,
        control_id: str,
        result: str,
    ) -> ProductionPauseControl:
        control = session.scalar(
            select(ProductionPauseControl).where(
                ProductionPauseControl.workspace_id == workspace_id,
                ProductionPauseControl.id == control_id,
            )
        )
        if control is None:
            raise TrialRunNotAllowedError(detail="暂停控制不存在")

        control.trial_completed_count = int(control.trial_completed_count) + 1
        if result == "PASS":
            control.trial_pass_count = int(control.trial_pass_count) + 1
        else:
            control.trial_fail_count = int(control.trial_fail_count) + 1
        control.updated_at = utc_now()

        if int(control.trial_fail_count) > 0:
            # 任一失败 → 重新暂停
            control.state = "PAUSED"
            control.trial_completed_count = 0
            control.trial_pass_count = 0
            control.trial_fail_count = 0
        elif int(control.trial_completed_count) >= int(control.trial_sku_limit):
            control.state = "RESOLVED"
            control.resolved_at = utc_now()

        session.flush()
        record_event(
            session,
            workspace_id=workspace_id,
            entity_type="PRODUCTION",
            entity_id=control.id,
            event_kind=GUARD_TRIAL_EVALUATED,
            payload={
                "result": result,
                "completed": control.trial_completed_count,
                "pass": control.trial_pass_count,
                "fail": control.trial_fail_count,
                "state": control.state,
            },
        )
        if control.state == "RESOLVED":
            record_event(
                session,
                workspace_id=workspace_id,
                entity_type="PRODUCTION",
                entity_id=control.id,
                event_kind=GUARD_RESOLVED,
                payload={"trigger_rule_id": control.trigger_rule_id},
            )
        session.flush()
        return control

    # ---------------- 概览 ----------------
    def status(self, *, session: Session, workspace_id: str) -> dict:
        pauses = self.active_pauses(session=session, workspace_id=workspace_id)
        evaluation = self.evaluate(session=session, workspace_id=workspace_id)
        return {
            "level": LEVEL_RED if pauses else evaluation.level,
            "evaluation": {
                "level": evaluation.level,
                "rule_id": evaluation.rule_id,
                "reason": evaluation.reason,
                "metrics": evaluation.metrics,
            },
            "pauses": [self._pause_brief(p) for p in pauses],
            "rules": dict(self.rules.data),
        }

    @staticmethod
    def _pause_brief(control: ProductionPauseControl) -> dict:
        return {
            "id": control.id,
            "scope_kind": control.scope_kind,
            "target": control.target,
            "state": control.state,
            "trigger_rule_id": control.trigger_rule_id,
            "rule_text": control.rule_text,
            "reason": control.reason,
            "paused_at": control.paused_at.isoformat() if control.paused_at else None,
            "updated_at": control.updated_at.isoformat() if control.updated_at else None,
            "trial_sku_limit": control.trial_sku_limit,
            "trial_claim_count": control.trial_claim_count,
            "trial_completed_count": control.trial_completed_count,
            "trial_pass_count": control.trial_pass_count,
            "trial_fail_count": control.trial_fail_count,
        }


def count_revisions_by_batch(*, session: Session, workspace_id: str, batch_id: str) -> int:
    return int(
        session.scalar(
            select(func.count())
            .select_from(ProductRevision)
            .where(ProductRevision.workspace_id == workspace_id, ProductRevision.batch_id == batch_id)
        )
        or 0
    )


__all__ = [
    "LEVEL_CRITICAL",
    "LEVEL_GREEN",
    "LEVEL_RED",
    "LEVEL_YELLOW",
    "GuardEvaluation",
    "ProductionGuardService",
    "SCOPE_PRODUCT_TYPE",
    "SCOPE_PROVIDER_MODEL",
    "SCOPE_SYSTEM",
]
