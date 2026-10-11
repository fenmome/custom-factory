"""模型包导出，供 Alembic 触发全量注册。"""

from __future__ import annotations

from app.models.audit import IdempotencyRecord, LifecycleEvent
from app.models.base import Base
from app.models.guard import ProductionPauseControl, SkuGenerationClaim
from app.models.image import ImageAsset, ImageAttempt, ImageJob, ImageQA, RevisionQA
from app.models.product import Batch, ListingConcept, Product, ProductRevision
from app.models.product_data import ProductData
from app.models.sku import ProductTypeSkuConfig
from app.models.title import TitleAsset, TitleReservation, TitleUsage
from app.models.workspace import User, Workspace, WorkspaceMembership

ALL_MODELS = (
    Workspace,
    User,
    WorkspaceMembership,
    ProductTypeSkuConfig,
    Batch,
    Product,
    ProductRevision,
    ListingConcept,
    ImageJob,
    ImageAttempt,
    ImageAsset,
    ImageQA,
    RevisionQA,
    ProductData,
    TitleAsset,
    TitleReservation,
    TitleUsage,
    SkuGenerationClaim,
    LifecycleEvent,
    ProductionPauseControl,
    IdempotencyRecord,
)

__all__ = [
    "ALL_MODELS",
    "Base",
    "Batch",
    "IdempotencyRecord",
    "ImageAsset",
    "ImageAttempt",
    "ImageJob",
    "ImageQA",
    "LifecycleEvent",
    "ListingConcept",
    "Product",
    "ProductData",
    "ProductRevision",
    "ProductTypeSkuConfig",
    "ProductionPauseControl",
    "RevisionQA",
    "SkuGenerationClaim",
    "TitleAsset",
    "TitleReservation",
    "TitleUsage",
    "User",
    "Workspace",
    "WorkspaceMembership",
]
