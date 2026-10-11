"""开发种子数据：默认工作空间 / 管理员 / 产品类型(SKU 配置) / 少量标题。

用法： `python -m scripts.seed`
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

from sqlalchemy import select

from app.core.database import SessionLocal, engine
from app.core.resource_loader import title_source
from app.core.security import hash_password
from app.models.audit import IdempotencyRecord  # noqa: F401
from app.models.base import Base
from app.models.product import Batch, Product, ProductRevision, ListingConcept
from app.models.sku import ProductTypeSkuConfig
from app.models.title import TitleAsset
from app.models.workspace import User, Workspace, WorkspaceMembership
from app.services.uuid_provider import new_uuid

DEFAULT_WORKSPACE_NAME = "Default Workspace"
ADMIN_EMAIL = "admin@custom-factory.com"
ADMIN_PASSWORD = "Admin@123456"

SEED_TITLES = [
    "Custom UV DTF Transfer Stickers for Small Business Packaging",
    "Personalized UV DTF Decal Stickers for Boutique Shipping Boxes",
    "Custom Logo UV DTF Transfers for Small Batch Product Packaging",
    "Made to Order UV DTF Transfer Stickers for Gift Box Branding",
    "Personalized Small Business Packaging Labels UV DTF Transfer",
]


def ensure_schema() -> None:
    Base.metadata.create_all(bind=engine)
    from alembic import command  # noqa: PLC0415
    from alembic.config import Config  # noqa: PLC0415

    cfg = Config("alembic.ini")
    try:
        command.stamp(cfg, "head")
    except Exception as exc:  # noqa: BLE001
        print(f"[seed] alembic stamp 跳过: {exc}")


def run() -> None:
    ensure_schema()
    session = SessionLocal()
    try:
        workspace = session.scalar(select(Workspace).where(Workspace.display_name == DEFAULT_WORKSPACE_NAME))
        if workspace is None:
            workspace = Workspace(id=new_uuid(), display_name=DEFAULT_WORKSPACE_NAME, state="ACTIVE")
            session.add(workspace)
            session.flush()

        user = session.scalar(select(User).where(User.email == ADMIN_EMAIL))
        if user is None:
            user = User(
                id=new_uuid(),
                email=ADMIN_EMAIL,
                password_hash=hash_password(ADMIN_PASSWORD),
                display_name="系统管理员",
                state="ACTIVE",
            )
            session.add(user)
            session.flush()

        membership = session.scalar(
            select(WorkspaceMembership).where(
                WorkspaceMembership.workspace_id == workspace.id,
                WorkspaceMembership.user_id == user.id,
            )
        )
        if membership is None:
            session.add(
                WorkspaceMembership(
                    id=new_uuid(),
                    workspace_id=workspace.id,
                    user_id=user.id,
                    role="OWNER",
                    status="ACTIVE",
                )
            )

        sku_config = session.scalar(
            select(ProductTypeSkuConfig).where(ProductTypeSkuConfig.prefix == "DZUVDTF")
        )
        if sku_config is None:
            session.add(
                ProductTypeSkuConfig(
                    id=new_uuid(),
                    workspace_id=workspace.id,
                    product_type_code="UV_DTF",
                    display_name="定制水晶标",
                    prefix="DZUVDTF",
                    sequence_width=6,
                    last_sequence=0,
                    is_enabled=True,
                )
            )

        pin = title_source()["source_pin"]
        for index, text in enumerate(SEED_TITLES, start=1):
            exists = session.scalar(select(TitleAsset).where(TitleAsset.title_text == text))
            if exists is not None:
                continue
            session.add(
                TitleAsset(
                    id=new_uuid(),
                    title_text=text,
                    editorial_status="CONTENT_QUALITY_APPROVED",
                    pool_version=pin["title_pool_version"],
                    source_sha=pin["title_source_hash"],
                    source_manifest_id=f"seed-manifest-{index:04d}",
                    query_id=f" SMALL_BUSINESS_Q{index:03d}".strip(),
                )
            )

        session.commit()
        print(json.dumps({"workspace_id": workspace.id, "email": ADMIN_EMAIL}, ensure_ascii=False))
    finally:
        session.close()


if __name__ == "__main__":
    sys.exit(run())
