from __future__ import annotations

from datetime import UTC, datetime, time
from typing import Annotated

from fastapi import APIRouter, Depends, HTTPException, Query, status
from redis.asyncio import Redis
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.comfyui.client import ComfyUIClient
from app.api.dependencies import require_password_changed
from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.asset import Asset
from app.models.user import User
from app.models.video_job import VideoJob
from app.schemas.video_job import (
    VideoJobCreate,
    VideoJobListResponse,
    VideoJobQueued,
    VideoJobResponse,
)
from app.services.workflows import WorkflowService


router = APIRouter(prefix="/video-jobs", tags=["video-jobs"])
QUEUE_KEY = "h3:video_jobs"
TERMINAL_STATUSES = {"completed", "failed", "cancelled"}


async def owned_job(db: AsyncSession, user: User, job_id: str) -> VideoJob:
    job = await db.get(VideoJob, job_id)
    if job is None or (job.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="任务不存在")
    return job


async def validate_assets(
    db: AsyncSession, user: User, mode: str, asset_ids: list[str]
) -> None:
    if mode in {"i2v", "ref2va"} and not asset_ids:
        detail = "图生视频必须上传首帧图片" if mode == "i2v" else "全能参考必须上传一张参考图片"
        raise HTTPException(status_code=422, detail=detail)
    if mode == "ref2va" and len(asset_ids) != 1:
        raise HTTPException(status_code=422, detail="当前全能参考仅支持一张参考图片")
    if not asset_ids:
        return
    assets = (
        await db.scalars(select(Asset).where(Asset.id.in_(asset_ids)))
    ).all()
    if len(assets) != len(set(asset_ids)) or any(asset.user_id != user.id for asset in assets):
        raise HTTPException(status_code=422, detail="素材不存在或无权使用")
    if mode in {"i2v", "ref2va"} and assets[0].kind != "image":
        detail = "首帧必须是图片素材" if mode == "i2v" else "参考素材必须是图片"
        raise HTTPException(status_code=422, detail=detail)


async def enqueue_job(
    payload: VideoJobCreate,
    user: User,
    db: AsyncSession,
    redis: Redis,
    *,
    parent_job_id: str | None = None,
) -> VideoJob:
    settings = get_settings()
    if payload.mode == "ref2va" and not settings.ref2va_enabled:
        raise HTTPException(status_code=422, detail="全能参考尚未启用")
    await validate_assets(db, user, payload.mode, payload.asset_ids)
    position = int(await redis.llen(QUEUE_KEY)) + 1
    job = VideoJob(
        user_id=user.id,
        parent_job_id=parent_job_id,
        mode=payload.mode,
        prompt=payload.prompt,
        negative_prompt=payload.negative_prompt,
        duration_seconds=payload.duration_seconds,
        aspect_ratio=payload.aspect_ratio,
        resolution=payload.resolution,
        seed=payload.seed,
        steps=payload.steps,
        flow_shift=payload.flow_shift,
        audio_flow_shift=payload.audio_flow_shift,
        input_assets=payload.asset_ids,
        workflow_name=f"h3_{payload.mode}_int8.json",
        workflow_version=WorkflowService.version,
        queue_position=position,
        progress=None,
        stage="排队中",
    )
    db.add(job)
    await db.flush()
    await redis.rpush(QUEUE_KEY, job.id)
    await db.commit()
    await db.refresh(job)
    return job


@router.post("", response_model=VideoJobQueued, status_code=201)
async def create_job(
    payload: VideoJobCreate,
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> VideoJobQueued:
    job = await enqueue_job(payload, user, db, redis)
    return VideoJobQueued(
        id=job.id,
        status=job.status,
        queue_position=job.queue_position or 1,
    )


@router.get("", response_model=VideoJobListResponse)
async def list_jobs(
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
    job_status: str | None = Query(default=None, alias="status"),
    mode: str | None = None,
    query: str | None = None,
    date_from: datetime | None = None,
    date_to: datetime | None = None,
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=20, ge=1, le=100),
) -> VideoJobListResponse:
    conditions = [VideoJob.user_id == user.id]
    if job_status:
        conditions.append(VideoJob.status == job_status)
    if mode:
        conditions.append(VideoJob.mode == mode)
    if query:
        conditions.append(VideoJob.prompt.ilike(f"%{query.strip()}%"))
    if date_from:
        conditions.append(VideoJob.created_at >= date_from)
    if date_to:
        conditions.append(VideoJob.created_at <= date_to)
    total = int(
        await db.scalar(select(func.count(VideoJob.id)).where(*conditions)) or 0
    )
    jobs = (
        await db.scalars(
            select(VideoJob)
            .where(*conditions)
            .order_by(VideoJob.created_at.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    ).all()
    return VideoJobListResponse(
        items=list(jobs), total=total, page=page, page_size=page_size
    )


@router.get("/{job_id}", response_model=VideoJobResponse)
async def get_job(
    job_id: str,
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> VideoJob:
    return await owned_job(db, user, job_id)


@router.post("/{job_id}/cancel", response_model=VideoJobResponse)
async def cancel_job(
    job_id: str,
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> VideoJob:
    job = await owned_job(db, user, job_id)
    if job.status in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="任务已经结束")
    if job.status == "queued":
        await redis.lrem(QUEUE_KEY, 1, job.id)
    elif job.status in {"switching", "preparing", "running", "encoding"}:
        await ComfyUIClient().interrupt()
    job.status = "cancelled"
    job.stage = "已取消"
    job.finished_at = datetime.now(UTC)
    await db.commit()
    await db.refresh(job)
    await redis.publish(f"h3:job:{job.id}", '{"status":"cancelled"}')
    return job


@router.post("/{job_id}/retry", response_model=VideoJobQueued, status_code=201)
async def retry_job(
    job_id: str,
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> VideoJobQueued:
    old_job = await owned_job(db, user, job_id)
    payload = VideoJobCreate(**old_job.parameters())
    job = await enqueue_job(payload, user, db, redis, parent_job_id=old_job.id)
    return VideoJobQueued(
        id=job.id,
        status=job.status,
        queue_position=job.queue_position or 1,
    )


@router.delete("/{job_id}", status_code=204)
async def delete_job(
    job_id: str,
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    job = await owned_job(db, user, job_id)
    if job.status not in TERMINAL_STATUSES:
        raise HTTPException(status_code=409, detail="只能删除已结束的任务")
    await db.delete(job)
    await db.commit()
