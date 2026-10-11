"""Initial schema (21 tables)

Revision ID: 0001_initial_schema
Revises:
Create Date: 2026-10-11

"""

from typing import Sequence, Union

import sqlalchemy as sa
from sqlalchemy.dialects import mysql

from alembic import op

revision: str = "0001_initial_schema"
down_revision: Union[str, None] = None
branch_labels: Union[str, Sequence[str], None] = None
depends_on: Union[str, Sequence[str], None] = None


UUID = mysql.CHAR(36)
TS = sa.DateTime(timezone=True)


def _pk() -> list[sa.Column]:
    return [sa.Column("id", UUID, primary_key=True)]


def _timestamps() -> list[sa.Column]:
    return [
        sa.Column("created_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
        sa.Column("updated_at", TS, nullable=False, server_default=sa.text("CURRENT_TIMESTAMP")),
    ]


def upgrade() -> None:
    # ---------------- workspace 域 ----------------
    op.create_table(
        "workspaces",
        *_pk(),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="ACTIVE"),
        *_timestamps(),
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "users",
        *_pk(),
        sa.Column("email", sa.String(255), nullable=False),
        sa.Column("password_hash", sa.String(255), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("is_superuser", sa.Boolean(), nullable=False, server_default="0"),
        *_timestamps(),
        sa.UniqueConstraint("email", name="uq_users_email"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_users_email", "users", ["email"])

    op.create_table(
        "workspace_memberships",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("user_id", UUID, nullable=False),
        sa.Column("role", sa.String(16), nullable=False, server_default="MEMBER"),
        sa.Column("status", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("joined_at", TS, nullable=False),
        sa.Column("revoked_at", TS, nullable=True),
        sa.UniqueConstraint("workspace_id", "user_id", name="uk_ws_user"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_workspace_memberships_workspace_id", "workspace_memberships", ["workspace_id"])
    op.create_index("ix_workspace_memberships_user_id", "workspace_memberships", ["user_id"])

    # ---------------- SKU 配置 ----------------
    op.create_table(
        "product_type_sku_configs",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("product_type_code", sa.String(64), nullable=False),
        sa.Column("display_name", sa.String(255), nullable=False),
        sa.Column("prefix", sa.String(32), nullable=False),
        sa.Column("sequence_width", sa.Integer(), nullable=False, server_default="6"),
        sa.Column("last_sequence", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("is_enabled", sa.Boolean(), nullable=False, server_default="1"),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "product_type_code", name="uk_ws_product_type"),
        sa.UniqueConstraint("prefix", name="uq_sku_prefix"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_product_type_sku_configs_workspace_id", "product_type_sku_configs", ["workspace_id"])

    # ---------------- 批次 / 商品 / 修订 / Concept ----------------
    op.create_table(
        "batches",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("product_type_id", UUID, nullable=False),
        sa.Column("requested_quantity", sa.Integer(), nullable=False),
        sa.Column("image_generation_route", sa.String(16), nullable=False, server_default="CODEX"),
        sa.Column("control_state", sa.String(32), nullable=False, server_default="ACTIVE"),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("input_snapshot_hash", mysql.CHAR(64), nullable=False),
        sa.Column("usage_code", sa.String(64), nullable=False),
        sa.Column("style_code", sa.String(64), nullable=True),
        sa.Column("palette_code", sa.String(32), nullable=True),
        sa.Column("prepared_at", TS, nullable=True),
        sa.Column("created_by_user_id", UUID, nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("workspace_id", "request_key", name="uk_request"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_batches_workspace_id", "batches", ["workspace_id"])
    op.create_index("ix_batches_product_type_id", "batches", ["product_type_id"])

    op.create_table(
        "products",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("batch_id", UUID, nullable=False),
        sa.Column("sku_namespace", UUID, nullable=False),
        sa.Column("internal_sku", sa.String(64), nullable=False),
        sa.Column("allocated_prefix", sa.String(32), nullable=False),
        sa.Column("allocated_sequence", sa.Integer(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="ACTIVE"),
        *_timestamps(),
        sa.UniqueConstraint("internal_sku", name="uk_sku"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_products_workspace_id", "products", ["workspace_id"])
    op.create_index("ix_products_batch_id", "products", ["batch_id"])

    op.create_table(
        "product_revisions",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("batch_id", UUID, nullable=False),
        sa.Column("revision_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("concept_id", UUID, nullable=True),
        sa.Column("status", sa.String(24), nullable=False, server_default="DRAFT"),
        sa.Column("image_policy_id", sa.String(64), nullable=True),
        sa.Column("image_policy_version", sa.String(32), nullable=True),
        sa.Column("image_policy_content_hash", mysql.CHAR(64), nullable=True),
        sa.Column("ready_gate_id", UUID, nullable=True),
        sa.Column("ready_at", TS, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("product_id", "revision_number", name="uk_product_rev"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_product_revisions_workspace_id", "product_revisions", ["workspace_id"])
    op.create_index("ix_product_revisions_product_id", "product_revisions", ["product_id"])
    op.create_index("ix_product_revisions_batch_id", "product_revisions", ["batch_id"])

    op.create_table(
        "listing_concepts",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("revision_id", UUID, nullable=False),
        sa.Column("title_id", UUID, nullable=True),
        sa.Column("title_text", sa.Text(), nullable=True),
        sa.Column("state", sa.String(16), nullable=False, server_default="DRAFT"),
        sa.Column("usage_code", sa.String(64), nullable=True),
        sa.Column("object", sa.String(64), nullable=True),
        sa.Column("use_case", sa.String(64), nullable=True),
        sa.Column("purpose", sa.Text(), nullable=True),
        sa.Column("product_profile_id", sa.String(64), nullable=True),
        sa.Column("semantic_payload_hash", mysql.CHAR(64), nullable=True),
        sa.Column("surface_gate", sa.JSON(), nullable=True),
        sa.Column("brand_name", sa.String(128), nullable=True),
        sa.Column("visual_plan", sa.JSON(), nullable=True),
        sa.Column("customization_constraints", sa.JSON(), nullable=True),
        sa.Column("fulfillment_constraints", sa.JSON(), nullable=True),
        sa.Column("core_hash", mysql.CHAR(64), nullable=True),
        *_timestamps(),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_listing_concepts_workspace_id", "listing_concepts", ["workspace_id"])
    op.create_index("ix_listing_concepts_revision_id", "listing_concepts", ["revision_id"])
    op.create_index("ix_listing_concepts_core_hash", "listing_concepts", ["core_hash"])

    # ---------------- 图片域 ----------------
    op.create_table(
        "image_jobs",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("revision_id", UUID, nullable=False),
        sa.Column("slot", sa.Integer(), nullable=False),
        sa.Column("role", sa.String(64), nullable=False),
        sa.Column("display_order", sa.Integer(), nullable=False),
        sa.Column("is_required", sa.Boolean(), nullable=False, server_default="0"),
        sa.Column("state", sa.String(24), nullable=False, server_default="PENDING"),
        sa.Column("control_generation", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("prompt_source_hash", mysql.CHAR(64), nullable=True),
        sa.Column("rendered_prompt", sa.Text(), nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("revision_id", "slot", name="uk_rev_slot"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_image_jobs_workspace_id", "image_jobs", ["workspace_id"])
    op.create_index("ix_image_jobs_revision_id", "image_jobs", ["revision_id"])

    op.create_table(
        "image_attempts",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("image_job_id", UUID, nullable=False),
        sa.Column("attempt_number", sa.Integer(), nullable=False, server_default="1"),
        sa.Column("state", sa.String(16), nullable=False, server_default="PENDING"),
        sa.Column("provider", sa.String(64), nullable=True),
        sa.Column("model", sa.String(128), nullable=True),
        sa.Column("prompt_source_git_revision", sa.String(255), nullable=True),
        sa.Column("prompt_version", sa.String(32), nullable=True),
        sa.Column("prompt_source_hash", mysql.CHAR(64), nullable=True),
        sa.Column("rendered_prompt", sa.Text(), nullable=True),
        sa.Column("error_code", sa.String(64), nullable=True),
        sa.Column("error_message", sa.Text(), nullable=True),
        sa.Column("settled_at", TS, nullable=True),
        *_timestamps(),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_image_attempts_workspace_id", "image_attempts", ["workspace_id"])
    op.create_index("ix_image_attempts_image_job_id", "image_attempts", ["image_job_id"])

    op.create_table(
        "image_assets",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("attempt_id", UUID, nullable=False),
        sa.Column("image_job_id", UUID, nullable=False),
        sa.Column("provenance_kind", sa.String(16), nullable=False, server_default="GENERATED"),
        sa.Column("integrity_state", sa.String(16), nullable=False, server_default="UNVERIFIED"),
        sa.Column("storage_profile", sa.String(64), nullable=False),
        sa.Column("storage_key", sa.String(512), nullable=False),
        sa.Column("checksum_algorithm", sa.String(16), nullable=False, server_default="sha256"),
        sa.Column("checksum_digest", mysql.CHAR(64), nullable=False),
        sa.Column("byte_size", mysql.BIGINT(), nullable=False),
        sa.Column("width", sa.Integer(), nullable=False),
        sa.Column("height", sa.Integer(), nullable=False),
        sa.Column("mime_type", sa.String(32), nullable=False, server_default="image/png"),
        *_timestamps(),
        sa.UniqueConstraint("attempt_id", name="uk_attempt"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_image_assets_workspace_id", "image_assets", ["workspace_id"])
    op.create_index("ix_image_assets_image_job_id", "image_assets", ["image_job_id"])

    op.create_table(
        "image_qa",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("asset_id", UUID, nullable=False),
        sa.Column("image_job_id", UUID, nullable=False),
        sa.Column("kind", sa.String(16), nullable=False),
        sa.Column("result", sa.String(8), nullable=False),
        sa.Column("reason_code", sa.String(64), nullable=True),
        sa.Column("reason_detail", sa.Text(), nullable=True),
        sa.Column("rule_id", sa.String(128), nullable=False),
        sa.Column("rule_version", sa.String(32), nullable=False),
        sa.Column("rule_hash", mysql.CHAR(64), nullable=False),
        sa.Column("asset_checksum", mysql.CHAR(64), nullable=False),
        sa.Column("operation_key", sa.String(128), nullable=False),
        sa.Column("overrides", sa.JSON(), nullable=True),
        sa.Column("evaluated_by", UUID, nullable=True),
        sa.Column("evaluated_at", TS, nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("asset_id", "rule_hash", "kind", "operation_key", name="uk_asset_rule"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_image_qa_workspace_id", "image_qa", ["workspace_id"])
    op.create_index("ix_image_qa_asset_id", "image_qa", ["asset_id"])
    op.create_index("ix_image_qa_image_job_id", "image_qa", ["image_job_id"])

    op.create_table(
        "revision_qa",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("revision_id", UUID, nullable=False),
        sa.Column("result", sa.String(8), nullable=False, server_default="PENDING"),
        sa.Column("passed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("failed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("pending_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("required_role_status", sa.JSON(), nullable=True),
        sa.Column("qa_result_snapshot", sa.JSON(), nullable=True),
        sa.Column("evaluated_at", TS, nullable=False),
        *_timestamps(),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_revision_qa_workspace_id", "revision_qa", ["workspace_id"])
    op.create_index("ix_revision_qa_revision_id", "revision_qa", ["revision_id"])

    # ---------------- 商品属性数据 ----------------
    op.create_table(
        "product_data",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("revision_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("concept_id", UUID, nullable=False),
        sa.Column("title_id", UUID, nullable=True),
        sa.Column("schema_id", sa.String(128), nullable=False),
        sa.Column("schema_version", sa.String(32), nullable=False),
        sa.Column("schema_hash", mysql.CHAR(64), nullable=False),
        sa.Column("data", sa.JSON(), nullable=False),
        sa.Column("manifest_hash", mysql.CHAR(64), nullable=True),
        sa.Column("qa_result_snapshot", sa.JSON(), nullable=True),
        sa.Column("state", sa.String(16), nullable=False, server_default="DRAFT"),
        *_timestamps(),
        sa.UniqueConstraint("revision_id", name="uk_revision_product_data"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_product_data_workspace_id", "product_data", ["workspace_id"])
    op.create_index("ix_product_data_product_id", "product_data", ["product_id"])

    # ---------------- 标题域 ----------------
    op.create_table(
        "title_assets",
        *_pk(),
        sa.Column("title_text", sa.Text(), nullable=False),
        sa.Column("editorial_status", sa.String(32), nullable=False, server_default="DRAFT"),
        sa.Column("pool_version", sa.String(32), nullable=False),
        sa.Column("source_sha", mysql.CHAR(64), nullable=False),
        sa.Column("source_manifest_id", sa.String(255), nullable=True),
        sa.Column("approval_overlay_id", sa.String(255), nullable=True),
        sa.Column("approval_overlay_hash", mysql.CHAR(64), nullable=True),
        sa.Column("query_id", sa.String(128), nullable=True),
        *_timestamps(),
        mysql_charset="utf8mb4",
    )

    op.create_table(
        "title_reservations",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("revision_id", UUID, nullable=False),
        sa.Column("title_id", UUID, nullable=False),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="RESERVED"),
        sa.Column("reserved_at", TS, nullable=True),
        sa.Column("used_at", TS, nullable=True),
        sa.Column("released_at", TS, nullable=True),
        *_timestamps(),
        sa.UniqueConstraint("product_id", name="uk_product_reservation"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_title_reservations_workspace_id", "title_reservations", ["workspace_id"])
    op.create_index("ix_title_reservations_revision_id", "title_reservations", ["revision_id"])
    op.create_index("ix_title_reservations_title_id", "title_reservations", ["title_id"])

    op.create_table(
        "title_usages",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("revision_id", UUID, nullable=False),
        sa.Column("title_id", UUID, nullable=False),
        sa.Column("title_text", sa.Text(), nullable=False),
        sa.Column("operation_key", sa.String(128), nullable=False),
        sa.Column("used_at", TS, nullable=False),
        *_timestamps(),
        sa.UniqueConstraint("operation_key", name="uq_title_usage_opkey"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_title_usages_workspace_id", "title_usages", ["workspace_id"])
    op.create_index("ix_title_usages_product_id", "title_usages", ["product_id"])
    op.create_index("ix_title_usages_revision_id", "title_usages", ["revision_id"])
    op.create_index("ix_title_usages_title_id", "title_usages", ["title_id"])

    # ---------------- 协调 / 保护 ----------------
    op.create_table(
        "sku_generation_claims",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("revision_id", UUID, nullable=False),
        sa.Column("product_id", UUID, nullable=False),
        sa.Column("batch_id", UUID, nullable=False),
        sa.Column("executor_kind", sa.String(8), nullable=False),
        sa.Column("executor_id", sa.String(128), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="ACTIVE"),
        sa.Column("request_key", sa.String(128), nullable=False),
        sa.Column("last_activity_at", TS, nullable=False),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("revision_id", "executor_kind", "executor_id", name="uk_rev_executor"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_sku_generation_claims_workspace_id", "sku_generation_claims", ["workspace_id"])
    op.create_index("ix_sku_generation_claims_revision_id", "sku_generation_claims", ["revision_id"])
    op.create_index("ix_sku_generation_claims_product_id", "sku_generation_claims", ["product_id"])
    op.create_index("ix_sku_generation_claims_batch_id", "sku_generation_claims", ["batch_id"])

    op.create_table(
        "production_pause_controls",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("scope_kind", sa.String(32), nullable=False),
        sa.Column("target", sa.JSON(), nullable=False),
        sa.Column("state", sa.String(16), nullable=False, server_default="PAUSED"),
        sa.Column("trigger_rule_id", sa.String(32), nullable=False),
        sa.Column("rule_text", sa.Text(), nullable=False),
        sa.Column("reason", sa.Text(), nullable=False),
        sa.Column("paused_at", TS, nullable=False),
        sa.Column("updated_at", TS, nullable=False),
        sa.Column("trial_sku_limit", sa.Integer(), nullable=False, server_default="3"),
        sa.Column("trial_claim_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trial_completed_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trial_pass_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("trial_fail_count", sa.Integer(), nullable=False, server_default="0"),
        sa.Column("resolved_at", TS, nullable=True),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_production_pause_controls_workspace_id", "production_pause_controls", ["workspace_id"])

    # ---------------- 审计 / 幂等 ----------------
    op.create_table(
        "lifecycle_events",
        sa.Column("id", mysql.BIGINT(), primary_key=True, autoincrement=True),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("entity_type", sa.String(64), nullable=False),
        sa.Column("entity_id", UUID, nullable=False),
        sa.Column("event_kind", sa.String(64), nullable=False),
        sa.Column("payload", sa.JSON(), nullable=True),
        sa.Column("occurred_at", TS, nullable=False),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_lifecycle_events_workspace_id", "lifecycle_events", ["workspace_id"])
    op.create_index("ix_lifecycle_events_occurred_at", "lifecycle_events", ["occurred_at"])

    op.create_table(
        "idempotency_records",
        *_pk(),
        sa.Column("workspace_id", UUID, nullable=False),
        sa.Column("operation_key", sa.String(128), nullable=False),
        sa.Column("scope", sa.String(64), nullable=False),
        sa.Column("request_fingerprint", mysql.CHAR(64), nullable=False),
        sa.Column("response_snapshot", sa.JSON(), nullable=True),
        sa.Column("created_at", TS, nullable=False),
        sa.UniqueConstraint("workspace_id", "operation_key", "scope", name="uk_ws_opkey_scope"),
        mysql_charset="utf8mb4",
    )
    op.create_index("ix_idempotency_records_workspace_id", "idempotency_records", ["workspace_id"])


def downgrade() -> None:
    for table in (
        "idempotency_records",
        "lifecycle_events",
        "production_pause_controls",
        "sku_generation_claims",
        "title_usages",
        "title_reservations",
        "title_assets",
        "product_data",
        "revision_qa",
        "image_qa",
        "image_assets",
        "image_attempts",
        "image_jobs",
        "listing_concepts",
        "product_revisions",
        "products",
        "batches",
        "product_type_sku_configs",
        "workspace_memberships",
        "users",
        "workspaces",
    ):
        op.drop_table(table)
