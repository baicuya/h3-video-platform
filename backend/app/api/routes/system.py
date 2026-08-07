from __future__ import annotations

import asyncio
import shutil
from typing import Annotated, Any

from fastapi import APIRouter, Depends
from redis.asyncio import Redis
from sqlalchemy import select, text
from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.comfyui.client import ComfyUIClient
from app.api.dependencies import require_admin
from app.core.config import get_settings
from app.core.database import get_db
from app.core.redis import get_redis
from app.models.user import User
from app.models.video_job import VideoJob


router = APIRouter(tags=["system"])


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
    redis: Annotated[Redis, Depends(get_redis)],
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
    usage = shutil.disk_usage(get_settings().storage_root.parent)
    return {
        "name": fields[0] if len(fields) > 0 else "unknown",
        "vram_used_mb": int(fields[1]) if len(fields) > 1 else None,
        "vram_total_mb": int(fields[2]) if len(fields) > 2 else None,
        "utilization_percent": int(fields[3]) if len(fields) > 3 else None,
        "temperature_c": int(fields[4]) if len(fields) > 4 else None,
        "current_job": current_job,
        "queue_length": int(await redis.llen("h3:video_jobs")),
        "disk": {
            "total": usage.total,
            "used": usage.used,
            "free": usage.free,
        },
    }


@router.get("/system/comfyui")
async def comfyui_status(
    _: Annotated[User, Depends(require_admin)],
) -> dict[str, Any]:
    return await ComfyUIClient().health_check()


@router.get("/system/queue")
async def queue_status(
    _: Annotated[User, Depends(require_admin)],
    redis: Annotated[Redis, Depends(get_redis)],
) -> dict[str, Any]:
    return {
        "paused": bool(await redis.get("h3:queue:paused")),
        "length": int(await redis.llen("h3:video_jobs")),
        "jobs": await redis.lrange("h3:video_jobs", 0, 99),
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
