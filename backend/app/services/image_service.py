"""图片任务管理：依据 Image Policy 创建 8 个槽位的 ImageJob。"""

from __future__ import annotations

from collections.abc import Sequence

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.exceptions import ValidationError
from app.core.resource_loader import Resource, image_policy
from app.models.image import ImageJob
from app.services.uuid_provider import new_uuid


def validate_policy_snapshot(*, policy: Resource | None = None) -> dict:
    """读取 Image Policy（禁止硬编码）。"""
    policy = policy or image_policy()
    return dict(policy.data)


def create_image_jobs(
    *,
    session: Session,
    workspace_id: str,
    revision_id: str,
    rendered_prompts: Sequence,
    policy: Resource | None = None,
) -> list[ImageJob]:
    """按 policy.slot_roles 创建 8 个任务并写入渲染后的 Prompt。"""
    policy = policy or image_policy()
    policy_roles = {int(entry["slot"]): entry for entry in policy["slot_roles"]}

    if len(rendered_prompts) != len(policy_roles):
        raise ValidationError(detail=f"渲染结果数量 {len(rendered_prompts)} != 策略槽位数 {len(policy_roles)}")

    jobs: list[ImageJob] = []
    for item in rendered_prompts:
        if int(item.slot) not in policy_roles:
            raise ValidationError(detail=f"未知槽位 {item.slot}")
        role_entry = policy_roles[int(item.slot)]
        if role_entry["role"] != item.role:
            raise ValidationError(detail=f"槽位 {item.slot} 角色不一致: {item.role} != {role_entry['role']}")

        existing = session.scalar(
            select(ImageJob).where(ImageJob.revision_id == revision_id, ImageJob.slot == int(item.slot))
        )
        if existing is not None:
            existing.rendered_prompt = item.prompt
            existing.prompt_source_hash = item.prompt_hash
            jobs.append(existing)
            continue

        job = ImageJob(
            id=new_uuid(),
            workspace_id=workspace_id,
            revision_id=revision_id,
            slot=int(item.slot),
            role=str(role_entry["role"]),
            display_order=int(role_entry["slot"]),
            is_required=bool(role_entry["is_required"]),
            state="PLANNED",
            prompt_source_hash=item.prompt_hash,
            rendered_prompt=item.prompt,
        )
        session.add(job)
        jobs.append(job)

    session.flush()
    return jobs


def attach_policy_snapshot(
    *,
    session: Session,
    revision,
    policy: Resource | None = None,
) -> None:
    policy = policy or image_policy()
    revision.image_policy_id = policy.data["policy_id"]
    revision.image_policy_version = policy.data["version"]
    revision.image_policy_content_hash = policy.content_hash
    session.flush()


def list_jobs(*, session: Session, workspace_id: str, revision_id: str) -> Sequence[ImageJob]:
    return session.scalars(
        select(ImageJob)
        .where(ImageJob.workspace_id == workspace_id, ImageJob.revision_id == revision_id)
        .order_by(ImageJob.slot)
    ).all()


def get_job(*, session: Session, workspace_id: str, image_job_id: str) -> ImageJob | None:
    return session.scalar(
        select(ImageJob).where(ImageJob.workspace_id == workspace_id, ImageJob.id == image_job_id)
    )


def get_job_by_slot(*, session: Session, workspace_id: str, revision_id: str, slot: int) -> ImageJob | None:
    return session.scalar(
        select(ImageJob).where(
            ImageJob.workspace_id == workspace_id,
            ImageJob.revision_id == revision_id,
            ImageJob.slot == slot,
        )
    )


def count_by_state(*, session: Session, revision_id: str, state: str) -> int:
    from sqlalchemy import func

    return int(
        session.scalar(
            select(func.count()).select_from(ImageJob).where(ImageJob.revision_id == revision_id, ImageJob.state == state)
        )
        or 0
    )
