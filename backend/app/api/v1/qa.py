"""质检与校准接口。"""

from __future__ import annotations

from collections.abc import Sequence

from fastapi import APIRouter, Depends, Query
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.response import ok
from app.deps import CurrentContext, get_current_context
from app.models.image import ImageAsset, ImageQA
from app.services.qa_calibration_service import QACalibrationService

router = APIRouter()


@router.get("/assets/{asset_id}/history", summary="某图片的完整 QA 历史（追加式）")
async def qa_history(
    asset_id: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    rows: Sequence[ImageQA] = db.scalars(
        select(ImageQA)
        .where(ImageQA.workspace_id == ctx.workspace_id, ImageQA.asset_id == asset_id)
        .order_by(ImageQA.evaluated_at.desc())
    ).all()
    items = [
        {
            "kind": row.kind,
            "result": row.result,
            "reason_code": row.reason_code,
            "reason_detail": row.reason_detail,
            "rule_id": row.rule_id,
            "rule_version": row.rule_version,
            "rule_hash": row.rule_hash,
            "asset_checksum": row.asset_checksum,
            "evaluated_by": row.evaluated_by,
            "evaluated_at": row.evaluated_at.isoformat() if row.evaluated_at else None,
        }
        for row in rows
    ]
    return ok({"asset_id": asset_id, "items": items})


@router.get("/false-positive-board", summary="误判看板（FALSE_PASS / FALSE_FAIL）")
async def false_positive_board(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    human_rows = db.scalars(
        select(ImageQA).where(ImageQA.workspace_id == ctx.workspace_id, ImageQA.kind == "HUMAN")
    ).all()

    false_pass: list[dict] = []
    false_fail: list[dict] = []
    for row in human_rows:
        auto = _latest_auto_result(db, row.asset_id)
        asset = db.get(ImageAsset, row.asset_id)
        entry = {
            "asset_id": row.asset_id,
            "checksum": row.asset_checksum,
            "human_result": row.result,
            "auto_result": auto,
            "reason_code": row.reason_code,
            "reason_detail": row.reason_detail,
            "storage_key": asset.storage_key if asset else None,
        }
        if auto is None:
            continue
        if row.result == "PASS" and auto == "FAIL":
            false_pass.append(entry)
        elif row.result == "FAIL" and auto == "PASS":
            false_fail.append(entry)

    return ok(
        {
            "false_pass": false_pass,
            "false_fail": false_fail,
            "false_pass_count": len(false_pass),
            "false_fail_count": len(false_fail),
        }
    )


@router.get("/calibration", summary="QA 校准报告")
async def calibration(
    product_type_id: str = Query(..., description="产品类型 ID"),
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    report = QACalibrationService().build_report(
        session=db, workspace_id=ctx.workspace_id, product_type_id=product_type_id
    )
    return ok(
        {
            "product_type_id": report.product_type_id,
            "batch_count": report.batch_count,
            "human_reviewed_images": report.human_reviewed_images,
            "agreement_rate": report.agreement_rate,
            "false_pass": report.false_pass,
            "false_fail": report.false_fail,
            "true_pass": report.true_pass,
            "true_fail": report.true_fail,
            "by_role": report.by_role,
            "by_reason": report.by_reason,
            "review_due": report.review_due,
        }
    )


@router.get("/calibration/due", summary="待触发规则复核的产品类型")
async def calibration_due(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    reports = QACalibrationService().due_reports(session=db, workspace_id=ctx.workspace_id)
    return ok(
        {
            "items": [
                {
                    "product_type_id": r.product_type_id,
                    "batch_count": r.batch_count,
                    "human_reviewed_images": r.human_reviewed_images,
                    "agreement_rate": r.agreement_rate,
                }
                for r in reports
            ]
        }
    )


def _latest_auto_result(db: Session, asset_id: str) -> str | None:
    row = db.scalar(
        select(ImageQA)
        .where(ImageQA.asset_id == asset_id, ImageQA.kind.in_(["TECHNICAL", "SEMANTIC"]))
        .order_by(ImageQA.evaluated_at.desc())
    )
    return row.result if row else None
