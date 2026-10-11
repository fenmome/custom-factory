"""API v1 路由聚合。

Base URL：`/api/v1`
"""

from __future__ import annotations

from fastapi import APIRouter

from app.api.v1 import (
    auth,
    batches,
    dashboard,
    guard,
    images,
    product_types,
    products,
    qa,
    reviews,
    workspace,
)

router = APIRouter()

router.include_router(auth.router, prefix="/auth", tags=["认证"])
router.include_router(workspace.router, prefix="/workspaces", tags=["工作空间"])
router.include_router(dashboard.router, prefix="/dashboard", tags=["生产总览"])
router.include_router(batches.router, prefix="/batches", tags=["批次"])
router.include_router(products.router, prefix="/products", tags=["商品"])
router.include_router(images.router, prefix="/images", tags=["图片"])
router.include_router(reviews.router, prefix="/reviews", tags=["复审"])
router.include_router(qa.router, prefix="/qa", tags=["质检"])
router.include_router(guard.router, prefix="/guard", tags=["生产保护"])
router.include_router(product_types.router, prefix="/product-types", tags=["产品类型"])

__all__ = ["router"]
