"""通用 Schema。"""

from __future__ import annotations

from pydantic import BaseModel, ConfigDict, Field


class OperationKeyMixin(BaseModel):
    """创建类操作的幂等键（UUID v4）。"""

    operation_key: str = Field(..., min_length=8, max_length=128, description="幂等键，UUID v4")


class PageParams(BaseModel):
    model_config = ConfigDict(arbitrary_types_allowed=True)

    page: int = Field(default=1, ge=1)
    page_size: int = Field(default=20, ge=1, le=200)

    @property
    def offset(self) -> int:
        return (self.page - 1) * self.page_size
