from __future__ import annotations

import asyncio
import os
import shutil
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import func, select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.comfyui.client import ComfyUIClient
from app.api.dependencies import require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.user import User
from app.models.video_job import VideoJob
from app.services.workflows import ASPECT_DIMENSIONS


router = APIRouter(tags=["system"])


def _read_cpu_times() -> tuple[int, int]:
    with open("/proc/stat", encoding="utf-8") as proc_stat:
        fields = proc_stat.readline().split()[1:]
    times = [int(value) for value in fields]
    idle = times[3] + (times[4] if len(times) > 4 else 0)
    return sum(times), idle


def _read_memory_status() -> dict[str, int | float]:
    values: dict[str, int] = {}
    with open("/proc/meminfo", encoding="utf-8") as meminfo:
        for line in meminfo:
            key, raw_value = line.split(":", 1)
            value = raw_value.strip().split()[0]
            values[key] = int(value) * 1024

    total = values["MemTotal"]
    available = values["MemAvailable"]
    used = total - available
    return {
        "total": total,
        "used": used,
        "available": available,
        "utilization_percent": round(used / total * 100, 1) if total else 0.0,
    }


async def _system_resources() -> dict[str, Any]:
    total_before, idle_before = _read_cpu_times()
    await asyncio.sleep(0.1)
    total_after, idle_after = _read_cpu_times()
    total_delta = total_after - total_before
    idle_delta = idle_after - idle_before
    cpu_percent = (
        round(max(0.0, min(100.0, (total_delta - idle_delta) / total_delta * 100)), 1)
        if total_delta > 0
        else 0.0
    )

    usage = shutil.disk_usage(get_settings().storage_root.parent)
    return {
        "cpu": {
            "utilization_percent": cpu_percent,
            "logical_cores": os.cpu_count() or 1,
        },
        "memory": _read_memory_status(),
        "disk": {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
            "utilization_percent": round(usage.used / usage.total * 100, 1)
            if usage.total
            else 0.0,
        },
    }


@router.get("/health")
async def health(
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict[str, str]:
    result = {"status": "ok", "database": "ok", "redis": "ok", "comfyui": "ok", "gpu": "ok"}
    try:
        await db.execute(text("SELECT 1"))
    except Exception:
        result["database"] = "error"
    try:
        await redis.ping()
    except Exception:
        result["redis"] = "error"
    try:
        await ComfyUIClient().health_check()
    except Exception:
        result["comfyui"] = "error"
    try:
        process = await asyncio.create_subprocess_exec(
            "nvidia-smi",
            "--query-gpu=name",
            "--format=csv,noheader",
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.DEVNULL,
        )
        if await process.wait() != 0:
            result["gpu"] = "error"
    except Exception:
        result["gpu"] = "error"
    if any(value == "error" for key, value in result.items() if key != "status"):
        result["status"] = "degraded"
    return result


@router.get("/system/gpu")
async def gpu_status(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> dict[str, Any]:
    query = (
        "name,memory.used,memory.total,utilization.gpu,temperature.gpu"
    )
    process = await asyncio.create_subprocess_exec(
        "nvidia-smi",
        f"--query-gpu={query}",
        "--format=csv,noheader,nounits",
        stdout=asyncio.subprocess.PIPE,
        stderr=asyncio.subprocess.PIPE,
    )
    stdout, _ = await process.communicate()
    fields = [part.strip() for part in stdout.decode().strip().split(",")]
    current_job = await db.scalar(
        select(VideoJob.id).where(VideoJob.status.in_(["preparing", "running", "encoding"]))
    )
    logical_queue_length = int(
        await db.scalar(select(func.count(VideoJob.id)).where(VideoJob.status == "queued")) or 0
    )
    resources = await _system_resources()
    return {
        "name": fields[0] if len(fields) > 0 else "unknown",
        "vram_used_mb": int(fields[1]) if len(fields) > 1 else None,
        "vram_total_mb": int(fields[2]) if len(fields) > 2 else None,
        "utilization_percent": int(fields[3]) if len(fields) > 3 else None,
        "temperature_c": int(fields[4]) if len(fields) > 4 else None,
        "current_job": current_job,
        "queue_length": logical_queue_length,
        **resources,
    }


@router.get("/system/comfyui")
async def comfyui_status(
    _: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    return await ComfyUIClient().health_check()


@router.get("/system/queue")
async def queue_status(
    _: Annotated[User, Depends(require_admin)],
    db: Annotated[AsyncSession, Depends(get_db)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict[str, Any]:
    pending_ids = await redis.lrange("h3:video_jobs", 0, 99)
    active_ids = list(
        (
            await db.scalars(
                select(VideoJob.id)
                .where(VideoJob.status.in_(["preparing", "running", "encoding"]))
                .order_by(VideoJob.started_at.asc(), VideoJob.created_at.asc())
            )
        ).all()
    )
    database_queued_ids = list(
        (
            await db.scalars(
                select(VideoJob.id)
                .where(VideoJob.status == "queued")
                .order_by(VideoJob.created_at.asc())
                .limit(100)
            )
        ).all()
    )
    ordered_ids = list(dict.fromkeys([*active_ids, *pending_ids, *database_queued_ids]))
    jobs_by_id: dict[str, tuple[VideoJob, User]] = {}
    if ordered_ids:
        rows = (
            await db.execute(
                select(VideoJob, User)
                .join(User, User.id == VideoJob.user_id)
                .where(VideoJob.id.in_(ordered_ids))
            )
        ).all()
        jobs_by_id = {job.id: (job, owner) for job, owner in rows}

    position_by_id = {job_id: index for index, job_id in enumerate(pending_ids, start=1)}
    jobs = []
    for job_id in ordered_ids:
        row = jobs_by_id.get(job_id)
        if row is None:
            continue
        job, owner = row
        width, height = ASPECT_DIMENSIONS.get(
            (job.aspect_ratio, job.resolution),
            ASPECT_DIMENSIONS.get((job.aspect_ratio, "480p"), (864, 480)),
        )
        jobs.append(
            {
                "id": job.id,
                "status": job.status,
                "queue_position": position_by_id.get(job.id),
                "queue_state": (
                    "running"
                    if job.id in active_ids
                    else "waiting"
                    if job.id in position_by_id
                    else "recovering"
                ),
                "mode": job.mode,
                "duration_seconds": job.duration_seconds,
                "aspect_ratio": job.aspect_ratio,
                "resolution": job.resolution,
                "generation_profile": job.generation_profile,
                "width": width,
                "height": height,
                "created_at": job.created_at,
                "started_at": job.started_at,
                "user_id": owner.id,
                "username": owner.username,
                "display_name": owner.display_name,
                "user_role": owner.role,
            }
        )
    return {
        "paused": bool(await redis.get("h3:queue:paused")),
        "length": len(database_queued_ids),
        "jobs": jobs,
    }


@router.post("/admin/queue/pause")
async def pause_queue(
    _: Annotated[User, Depends(require_admin)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict[str, bool]:
    await redis.set("h3:queue:paused", "1")
    return {"paused": True}


@router.post("/admin/queue/resume")
async def resume_queue(
    _: Annotated[User, Depends(require_admin)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict[str, bool]:
    await redis.delete("h3:queue:paused")
    return {"paused": False}
