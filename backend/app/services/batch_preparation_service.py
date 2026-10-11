"""批次生产准备编排（功能说明书 2.2）。

对每个 SKU 依次执行：
1. 标题分配（AVAILABLE → RESERVED）
2. Primary 语义解析（仅 Primary Query）
3. 对象解析（优先级 + HOLD + 兜底）
4. 概念冻结（写 ListingConcept，计算 core_hash）
5. 渲染提示词（8 槽位）
6. 创建图片任务（8 个 ImageJob）
7. 发布冻结计划（`codex-image-task-v1`）
"""

from __future__ import annotations

from dataclasses import dataclass

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.events import (
    BATCH_PREPARED,
    CONCEPT_FROZEN,
    IMAGE_JOBS_CREATED,
    record_event,
    utc_now,
)
from app.core.exceptions import BatchNotFoundError
from app.core.hashing import core_hash
from app.core.resource_loader import image_policy, title_source, visual_preparation
from app.models.product import Batch, ListingConcept, Product, ProductRevision
from app.models.title import TitleAsset
from app.services import image_service, title_service
from app.services.brand_generator import BrandGenerator
from app.services.frozen_sku_plan_store import FrozenSkuPlanStore
from app.services.object_resolver import ObjectResolver
from app.services.primary_visual_semantic_service import PrimaryVisualSemanticService
from app.services.prompt_renderer import FrozenArtworkFacts, PromptRenderer
from app.services.sku_service import list_configs
from app.services.uuid_provider import new_uuid

PLAN_PACKAGE = "codex-image-task-v1"


@dataclass(frozen=True)
class PreparationResult:
    batch_id: str
    prepared_count: int
    skipped_count: int
    plan_count: int
    errors: list[dict[str, str]]


class BatchProductionPreparationService:
    def __init__(
        self,
        *,
        plan_store: FrozenSkuPlanStore | None = None,
        brands: BrandGenerator | None = None,
        semantic: PrimaryVisualSemanticService | None = None,
        resolver: ObjectResolver | None = None,
        renderer: PromptRenderer | None = None,
    ) -> None:
        self.plan_store = plan_store or FrozenSkuPlanStore()
        self.brands = brands or BrandGenerator()
        self.semantic = semantic or PrimaryVisualSemanticService()
        self.resolver = resolver or ObjectResolver()
        self.renderer = renderer or PromptRenderer()

    def prepare_batch(
        self,
        *,
        session: Session,
        workspace_id: str,
        batch_id: str,
        operation_key: str,
    ) -> PreparationResult:
        batch = session.scalar(
            select(Batch).where(Batch.workspace_id == workspace_id, Batch.id == batch_id)
        )
        if batch is None:
            raise BatchNotFoundError(detail=f"batch_id={batch_id}")

        revisions = session.scalars(
            select(ProductRevision)
            .where(ProductRevision.workspace_id == workspace_id, ProductRevision.batch_id == batch_id)
            .order_by(ProductRevision.created_at)
        ).all()

        pin = title_source()["source_pin"]
        pool_version = pin["title_pool_version"]

        brand_names = self.brands.generate_for_batch(
            session=session, workspace_id=workspace_id, batch_id=batch_id, quantity=len(revisions)
        )

        configs = {c.id: c for c in list_configs(session=session, workspace_id=workspace_id)}

        prepared = 0
        skipped = 0
        plans = 0
        errors: list[dict[str, str]] = []

        for index, revision in enumerate(revisions):
            try:
                planned = self._prepare_revision(
                    session=session,
                    workspace_id=workspace_id,
                    batch=batch,
                    revision=revision,
                    brand_name=brand_names[index],
                    prefix=configs.get(batch.product_type_id).prefix if configs.get(batch.product_type_id) else "SKU",
                    pool_version=pool_version,
                    operation_key=f"{operation_key}:{revision.id}",
                )
                if planned:
                    prepared += 1
                    plans += 1
                else:
                    skipped += 1
            except Exception as exc:  # noqa: BLE001 - 单 SKU 失败不阻断整批
                errors.append({"revision_id": revision.id, "error": str(exc)})

        batch.prepared_at = utc_now()
        session.flush()

        record_event(
            session,
            workspace_id=workspace_id,
            entity_type="BATCH",
            entity_id=batch_id,
            event_kind=BATCH_PREPARED,
            payload={"prepared": prepared, "skipped": skipped, "errors": errors},
        )
        session.flush()
        return PreparationResult(
            batch_id=batch_id, prepared_count=prepared, skipped_count=skipped, plan_count=plans, errors=errors
        )

    # ---------------- 单 SKU ----------------
    def _prepare_revision(
        self,
        *,
        session: Session,
        workspace_id: str,
        batch: Batch,
        revision: ProductRevision,
        brand_name: str,
        prefix: str,
        pool_version: str,
        operation_key: str,
    ) -> bool:
        product = session.scalar(
            select(Product).where(Product.id == revision.product_id, Product.workspace_id == workspace_id)
        )
        if product is None:
            return False

        concept = session.scalar(select(ListingConcept).where(ListingConcept.id == revision.concept_id))
        if concept is None:
            return False
        if concept.state == "FROZEN":
            return False

        # 1) 标题分配
        core_draft = core_hash(product.internal_sku, batch.usage_code, brand_name)
        reservation = title_service.reserve_for_revision(
            session=session,
            workspace_id=workspace_id,
            product_id=product.id,
            revision_id=revision.id,
            core_hash=core_draft,
            request_key=f"{batch.request_key}:{product.internal_sku}",
            pool_version=pool_version,
        )

        asset = session.get(TitleAsset, reservation.title_id)
        title_text = asset.title_text if asset else ""

        # 2) Primary 语义（禁止 Secondary 文本进入）
        extracted = self.semantic.extract(
            query_id=asset.query_id if asset and asset.query_id else f"Q-{product.internal_sku}",
            query_text=title_text,
            use_case=batch.usage_code,
            motif_candidates=visual_preparation()["motifs"],
        )

        # 3) 对象解析
        resolution = self.resolver.resolve(
            primary_objects=extracted.objects,
            secondary_objects=None,
            allow_fallback=True,
        )

        # 4) 概念冻结
        style = self.renderer.resolve_style(batch.style_code)
        palette = self.renderer.resolve_palette(batch.palette_code)

        concept.title_id = asset.id if asset else None
        concept.title_text = title_text
        concept.state = "FROZEN"
        concept.object = resolution.object
        concept.use_case = extracted.use_case
        concept.purpose = extracted.query_text
        concept.product_profile_id = None
        concept.semantic_payload_hash = None
        concept.surface_gate = resolution.surface_gate
        concept.brand_name = brand_name
        concept.visual_plan = {
            "style": style,
            "palette": palette,
            "palette_code": batch.palette_code,
            "style_code": batch.style_code,
            "logo_motif": extracted.motif_candidates[0] if extracted.motif_candidates else "minimal shop mark icon",
            "variant": self._pick_variant(resolution.object),
        }
        concept.customization_constraints = {
            "recommended_upload_format": "PNG",
            "accepted_upload_formats": ["JPG", "PNG"],
            "transparent_background_recommended": True,
            "reject": ["blurry screenshots", "low-quality artwork"],
        }
        concept.fulfillment_constraints = {
            "sold_entity": "Custom UV DTF transfer / decal",
            "carrier_not_supplied": True,
            "carrier": resolution.object,
        }
        concept.core_hash = core_hash(
            product.internal_sku,
            batch.usage_code,
            title_text,
            resolution.object,
            brand_name,
            style,
        )
        session.flush()

        revision.status = "FROZEN"
        session.flush()

        record_event(
            session,
            workspace_id=workspace_id,
            entity_type="REVISION",
            entity_id=revision.id,
            event_kind=CONCEPT_FROZEN,
            payload={"core_hash": concept.core_hash, "object": resolution.object},
        )

        # 5) 渲染提示词
        facts = FrozenArtworkFacts(
            brand_name=brand_name,
            style=style,
            palette=palette,
            logo_motif=str(concept.visual_plan["logo_motif"]),
            surface_gate=resolution.surface_gate,
        )
        rendered = self.renderer.render(
            semantic=extracted.payload(),
            resolved_object=resolution.object,
            facts=facts,
            presentation_variant=concept.visual_plan.get("variant"),
        )

        # 6) 创建图片任务
        policy = image_policy()
        image_service.attach_policy_snapshot(session=session, revision=revision, policy=policy)
        jobs = image_service.create_image_jobs(
            session=session,
            workspace_id=workspace_id,
            revision_id=revision.id,
            rendered_prompts=rendered,
            policy=policy,
        )
        record_event(
            session,
            workspace_id=workspace_id,
            entity_type="REVISION",
            entity_id=revision.id,
            event_kind=IMAGE_JOBS_CREATED,
            payload={"jobs": len(jobs)},
        )

        # 7) 冻结计划
        plan_package = self._build_plan(
            workspace_id=workspace_id,
            batch=batch,
            product=product,
            revision=revision,
            concept=concept,
            jobs=jobs,
            rendered=rendered,
            prefix=prefix,
            resolution=resolution,
        )
        self.plan_store.save(workspace_id=workspace_id, revision_id=revision.id, package=plan_package)
        session.flush()
        return True

    @staticmethod
    def _pick_variant(resolved_object: str) -> dict:
        variants = visual_preparation()["presentation_variants"]
        for variant in variants:
            if resolved_object in variant["allowed_objects"]:
                return dict(variant)
        return dict(variants[-1])

    @staticmethod
    def _build_plan(
        *,
        workspace_id: str,
        batch: Batch,
        product: Product,
        revision: ProductRevision,
        concept: ListingConcept,
        jobs,
        rendered,
        prefix: str,
        resolution,
    ) -> dict:
        role_by_slot = {int(item.slot): item.role for item in rendered}
        return {
            "plan_format": PLAN_PACKAGE,
            "workspace_id": workspace_id,
            "batch_id": batch.id,
            "product_id": product.id,
            "revision_id": revision.id,
            "internal_sku": product.internal_sku,
            "prefix": prefix,
            "core_hash": concept.core_hash,
            "object": resolution.object,
            "object_source": resolution.source,
            "brand_name": concept.brand_name,
            "visual_plan": concept.visual_plan,
            "surface_gate": concept.surface_gate,
            "customization_constraints": concept.customization_constraints,
            "fulfillment_constraints": concept.fulfillment_constraints,
            "image_policy": {
                "policy_id": revision.image_policy_id,
                "version": revision.image_policy_version,
                "hash": revision.image_policy_content_hash,
            },
            "operation_key": new_uuid(),
            "jobs": [
                {
                    "slot": job.slot,
                    "role": role_by_slot.get(job.slot, job.role),
                    "is_required": job.is_required,
                    "prompt": job.rendered_prompt,
                    "prompt_hash": job.prompt_source_hash,
                    "storage_key_hint": f"{prefix}/{product.internal_sku}/{product.internal_sku}-{job.slot:02d}.png",
                }
                for job in jobs
            ],
        }
