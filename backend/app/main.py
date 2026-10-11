"""Custom Factory API 入口。"""

from __future__ import annotations

import logging

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware
from fastapi.responses import JSONResponse

from app.config import settings
from app.core.error_handlers import register_exception_handlers
from app.core.resource_loader import iter_manifest
from app.core.response import ok

logging.basicConfig(level=logging.INFO, format="%(asctime)s %(levelname)s %(name)s %(message)s")
logger = logging.getLogger("custom_factory")

# 生产环境关闭 Swagger（agent.md 第 10 节）
DOCS_URL = None if settings.is_production else "/api/docs"
OPENAPI_URL = None if settings.is_production else "/api/openapi.json"


def create_app() -> FastAPI:
    from app.api.runner.endpoints import router as runner_router
    from app.api.v1 import router as v1_router

    app = FastAPI(
        title="Custom Factory API",
        version="1.0.0",
        description="定制商品生产系统 —— 批次/SKU/图片/质检/READY 全流程",
        docs_url=DOCS_URL,
        redoc_url=None,
        openapi_url=OPENAPI_URL,
    )

    app.add_middleware(
        CORSMiddleware,
        allow_origins=settings.CORS_ORIGINS,
        allow_credentials=settings.CORS_ALLOW_CREDENTIALS,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    register_exception_handlers(app)

    app.include_router(v1_router, prefix="/api/v1")
    # Runner API（内部，仅本机回环）
    app.include_router(runner_router, prefix="/internal/runner")

    @app.get("/api/health", tags=["系统"], summary="健康检查")
    async def health() -> JSONResponse:
        return JSONResponse(content=ok({"status": "ok", "environment": settings.ENVIRONMENT}))

    @app.on_event("startup")
    async def _startup() -> None:
        try:
            resources = iter_manifest()
            logger.info("已加载 %d 个业务资源文件", len(resources))
        except Exception:  # noqa: BLE001 - 资源缺失不应阻断启动诊断
            logger.warning("业务资源加载失败，请检查 app/resources 目录", exc_info=True)

    return app


app = create_app()
