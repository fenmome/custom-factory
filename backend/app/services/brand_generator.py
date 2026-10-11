"""冻结品牌名生成器。

规则来自 `visual_prep/visual_preparation_v1.json`：
- 批次内不重复（NO_DUPLICATE_HARD）
- 优先使用未使用过的组合（UNUSED_FIRST_BEST_EFFORT）
- 组合：`prefix + core + suffix`（排除 excluded_cores）
- 池耗尽 → HOLD_BRAND_POOL_EXHAUSTED
"""

from __future__ import annotations

import random
from itertools import product

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import AppError
from app.core.resource_loader import Resource, visual_preparation
from app.models.product import ListingConcept, ProductRevision


class BrandPoolExhausted(AppError):
    code = 50021
    default_message = "HOLD_BRAND_POOL_EXHAUSTED"


class BrandGenerator:
    def __init__(self, *, resource: Resource | None = None, seed: int | None = None) -> None:
        self.resource = resource or visual_preparation()
        brand = self.resource["brand"]
        self.prefixes: list[str] = list(brand["prefixes"])
        self.cores: list[str] = [c for c in brand["cores"] if c not in set(brand["excluded_cores"])]
        self.suffixes: list[str] = list(brand["suffixes"])
        self.random = random.Random(seed)  # noqa: S311 - 非密码学用途

    @property
    def capacity(self) -> int:
        return len(self.prefixes) * len(self.cores) * len(self.suffixes)

    def all_candidates(self) -> list[str]:
        return [f"{p} {c} {s}" for p, c, s in product(self.prefixes, self.cores, self.suffixes)]

    def generate_for_batch(
        self,
        *,
        session: Session,
        workspace_id: str,
        batch_id: str,
        quantity: int,
    ) -> list[str]:
        """为一个批次一次性生成互不重复的品牌名。"""
        if quantity <= 0:
            return []
        if quantity > self.capacity:
            raise BrandPoolExhausted(detail=f"请求 {quantity} > 池容量 {self.capacity}")

        used_in_batch = self._used_in_batch(session=session, batch_id=batch_id)
        history = self._used_in_workspace(session=session, workspace_id=workspace_id)

        candidates = self.all_candidates()
        # UNUSED_FIRST_BEST_EFFORT：历史未使用优先，再打散
        fresh = [c for c in candidates if c not in history]
        already = [c for c in candidates if c not in fresh]
        self.random.shuffle(fresh)
        self.random.shuffle(already)

        chosen: list[str] = []
        for pool in (fresh, already):
            for name in pool:
                if len(chosen) >= quantity:
                    break
                if name in used_in_batch:
                    continue
                chosen.append(name)
            if len(chosen) >= quantity:
                break

        if len(chosen) < quantity:
            raise BrandPoolExhausted(detail=f"仅能生成 {len(chosen)}/{quantity}")
        return chosen

    @staticmethod
    def _used_in_batch(*, session: Session, batch_id: str) -> set[str]:
        stmt = (
            select(ListingConcept.brand_name)
            .join(ProductRevision, ListingConcept.revision_id == ProductRevision.id)
            .where(ProductRevision.batch_id == batch_id, ListingConcept.brand_name.is_not(None))
        )
        return set(session.scalars(stmt).all())

    @staticmethod
    def _used_in_workspace(*, session: Session, workspace_id: str) -> set[str]:
        stmt = select(ListingConcept.brand_name).where(
            ListingConcept.workspace_id == workspace_id,
            ListingConcept.brand_name.is_not(None),
        )
        return set(session.scalars(stmt).all())
