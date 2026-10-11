"""产品类型（SKU 配置）接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from pydantic import BaseModel, Field
from sqlalchemy.orm import Session

from app.core.database import get_session
from app.core.exceptions import ValidationError
from app.core.response import ok
from app.deps import CurrentContext, get_current_context, require_admin
from app.schemas.product import ProductTypeResponse, ProductTypeUpsert
from app.services import sku_service

router = APIRouter()


class SequenceWidthPatch(BaseModel):
    sequence_width: int = Field(..., ge=1, le=12)
    is_enabled: bool | None = None


@router.get("", summary="产品类型列表")
async def list_types(
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    rows = sku_service.list_configs(session=db, workspace_id=ctx.workspace_id)
    items = [
        ProductTypeResponse(
            id=row.id,
            product_type_code=row.product_type_code,
            display_name=row.display_name,
            prefix=row.prefix,
            sequence_width=row.sequence_width,
            last_sequence=row.last_sequence,
            is_enabled=row.is_enabled,
            created_at=row.created_at,
        ).model_dump()
        for row in rows
    ]
    return ok({"items": items, "total": len(items)})


@router.post("", summary="创建产品类型 SKU 配置")
async def create_type(
    payload: ProductTypeUpsert,
    ctx: CurrentContext = Depends(require_admin),
    db: Session = Depends(get_session),
):
    config = sku_service.create_config(
        session=db,
        workspace_id=ctx.workspace_id,
        product_type_code=payload.product_type_code,
        display_name=payload.display_name,
        prefix=payload.prefix,
        sequence_width=payload.sequence_width,
    )
    db.commit()
    return ok(_response(config))


@router.patch("/{product_type_code}", summary="修改显示名 / 流水号位数 / 启用状态")
async def update_type(
    product_type_code: str,
    payload: SequenceWidthPatch,
    ctx: CurrentContext = Depends(require_admin),
    db: Session = Depends(get_session),
):
    config = sku_service.get_config(
        session=db, workspace_id=ctx.workspace_id, product_type_code=product_type_code
    )
    updated = sku_service.update_config(
        session=db,
        config=config,
        sequence_width=payload.sequence_width,
        is_enabled=payload.is_enabled,
    )
    db.commit()
    return ok(_response(updated))


@router.get("/{product_type_code}/next-preview", summary="预览下一个可用 SKU")
async def preview_next(
    product_type_code: str,
    ctx: CurrentContext = Depends(get_current_context),
    db: Session = Depends(get_session),
):
    config = sku_service.get_config(
        session=db, workspace_id=ctx.workspace_id, product_type_code=product_type_code
    )
    if config.prefix is None:
        raise ValidationError(detail="尚未分配前缀")
    next_sku = sku_service.format_sku(
        prefix=config.prefix, sequence=config.last_sequence + 1, width=config.sequence_width
    )
    return ok({"product_type_code": product_type_code, "next_sku": next_sku})


def _response(config) -> dict:
    return ProductTypeResponse(
        id=config.id,
        product_type_code=config.product_type_code,
        display_name=config.display_name,
        prefix=config.prefix,
        sequence_width=config.sequence_width,
        last_sequence=config.last_sequence,
        is_enabled=config.is_enabled,
        created_at=config.created_at,
    ).model_dump()
