"""统一 API 响应模型。

成功：`{"code": 0, "message": "success", "data": {...}}`
错误：`{"code": 40001, "message": "...", "detail": "..."}`
"""

from __future__ import annotations

from typing import Any, Generic, TypeVar

from pydantic import BaseModel, Field

T = TypeVar("T")

SUCCESS_CODE = 0


class ApiResponse(BaseModel, Generic[T]):
    code: int = SUCCESS_CODE
    message: str = "success"
    data: T | None = None
    detail: Any = None


class PageMeta(BaseModel):
    page: int = 1
    page_size: int = 20
    total: int = 0

    @property
    def total_page(self) -> int:
        if self.page_size <= 0:
            return 0
        return (self.total + self.page_size - 1) // self.page_size


class PageData(BaseModel, Generic[T]):
    items: list[T] = Field(default_factory=list)
    total: int = 0
    page: int = 1
    page_size: int = 20


def ok(data: Any = None, *, message: str = "success") -> dict[str, Any]:
    return {"code": SUCCESS_CODE, "message": message, "data": data}


def paged(
    items: list[Any],
    *,
    total: int,
    page: int,
    page_size: int,
) -> dict[str, Any]:
    return {
        "code": SUCCESS_CODE,
        "message": "success",
        "data": {
            "items": items,
            "total": total,
            "page": page,
            "page_size": page_size,
        },
    }
