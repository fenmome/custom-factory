"""全局异常处理器：把 AppError 转成统一响应格式。"""

from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from pydantic import ValidationError as PydanticValidationError

from app.core.exceptions import AppError, IdempotencyReplay
from app.core.response import SUCCESS_CODE, ok

logger = logging.getLogger("custom_factory")


def _error_body(*, code: int, message: str, detail=None) -> JSONResponse:
    return JSONResponse(
        status_code=200 if code == 0 else _status_for(code),
        content={"code": code, "message": message, "data": None, "detail": detail},
    )


def _status_for(code: int) -> int:
    """由业务错误码推断 HTTP 状态码（与 exceptions 中声明保持一致）。"""
    from app.core import exceptions

    for name in dir(exceptions):
        obj = getattr(exceptions, name)
        if isinstance(obj, type) and issubclass(obj, AppError) and getattr(obj, "code", None) == code:
            return int(getattr(obj, "http_status", 400))
    return 400


def register_exception_handlers(app: FastAPI) -> None:
    @app.exception_handler(AppError)
    async def _handle_app_error(_: Request, exc: AppError) -> JSONResponse:
        return _error_body(code=exc.code, message=exc.message, detail=exc.detail)

    @app.exception_handler(IdempotencyReplay)
    async def _handle_replay(_: Request, exc: IdempotencyReplay) -> JSONResponse:
        return JSONResponse(
            status_code=200,
            content={"code": SUCCESS_CODE, "message": "请求已处理（幂等重放）", "data": exc.detail},
        )

    @app.exception_handler(RequestValidationError)
    async def _handle_fastapi_validation(_: Request, exc: RequestValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={
                "code": 40001,
                "message": "请求参数校验失败",
                "data": None,
                "detail": [
                    {"loc": list(map(str, e["loc"])), "msg": e["msg"]} for e in exc.errors()
                ],
            },
        )

    @app.exception_handler(PydanticValidationError)
    async def _handle_pydantic_validation(_: Request, exc: PydanticValidationError) -> JSONResponse:
        return JSONResponse(
            status_code=422,
            content={"code": 40001, "message": "数据校验失败", "data": None, "detail": exc.errors()},
        )

    @app.exception_handler(Exception)
    async def _handle_unexpected(_: Request, exc: Exception) -> JSONResponse:
        logger.exception("未处理异常: %s", exc)
        return JSONResponse(
            status_code=500,
            content={"code": 50000, "message": "服务器内部错误", "data": None, "detail": str(exc)},
        )


__all__ = ["ok", "register_exception_handlers"]
