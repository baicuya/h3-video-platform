from __future__ import annotations

import asyncio
import json
import logging
from datetime import UTC, datetime
from pathlib import Path
from typing import Any

from sqlalchemy.ext.asyncio import AsyncSession

from app.adapters.comfyui.client import ComfyUIClient
from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.redis import redis_client
from app.models.asset import Asset
from app.models.video_job import VideoJob
from app.services.storage import LocalStorageProvider
from app.services.workflows import WorkflowService


logger = logging.getLogger("h3.worker")
QUEUE_KEY = "h3:video_jobs"
GPU_LOCK_KEY = "h3:gpu:lock"


async def publish(job: VideoJob) -> None:
    await redis_client.publish(
        f"h3:job:{job.id}",
        json.dumps(
            {
                "id": job.id,
                "status": job.status,
                "progress": job.progress,
                "stage": job.stage,
                "error_code": job.error_code,
            }
        ),
    )


async def update_job(
    db: AsyncSession,
    job: VideoJob,
    *,
    status: str | None = None,
    stage: str | None = None,
    progress: float | None = None,
) -> None:
    if status is not None:
        job.status = status
    if stage is not None:
        job.stage = stage
    if progress is not None:
        job.progress = progress
    await db.commit()
    await publish(job)


def first_output(history_item: dict[str, Any]) -> dict[str, Any]:
    for output in history_item.get("outputs", {}).values():
        for item in output.get("images", []):
            if item.get("filename", "").lower().endswith((".mp4", ".webm", ".mov")):
                return item
    raise FileNotFoundError("ComfyUI output video was not found")


async def process_job(job_id: str) -> None:
    settings = get_settings()
    storage = LocalStorageProvider(settings.storage_root)
    client = ComfyUIClient()
    workflow_service = WorkflowService()

    async with SessionLocal() as db:
        job = await db.get(VideoJob, job_id)
        if job is None or job.status != "queued":
            return
        job.started_at = datetime.now(UTC)
        await update_job(db, job, status="preparing", stage="准备素材")
        try:
            comfy_image_name = None
            if job.mode in {"i2v", "ref2va"}:
                asset_id = job.input_assets[0]
                asset = await db.get(Asset, asset_id)
                if asset is None:
                    raise ValueError("INVALID_ASSET: input image is missing")
                comfy_image_name = await client.upload_image(
                    storage.absolute_path(asset.storage_path)
                )
            workflow = workflow_service.build(job, comfy_image_name)
            prompt_id = await client.submit_workflow(workflow)
            job.comfy_prompt_id = prompt_id
            await update_job(db, job, status="running", stage="生成中")

            async for event in client.watch_execution(prompt_id):
                if job.status == "cancelled":
                    return
                if event.get("type") == "progress":
                    data = event.get("data", {})
                    value, maximum = data.get("value"), data.get("max")
                    if isinstance(value, int) and isinstance(maximum, int) and maximum > 0:
                        await update_job(
                            db,
                            job,
                            stage=f"生成中 · Step {value} / {maximum}",
                            progress=value / maximum,
                        )
            history = await client.get_history(prompt_id)
            history_item = history.get(prompt_id)
            if not history_item or history_item.get("status", {}).get("status_str") != "success":
                raise RuntimeError("GENERATION_FAILED: ComfyUI did not report success")
            await update_job(db, job, status="encoding", stage="视频编码")
            output = first_output(history_item)
            video_bytes = await client.view_file(
                filename=output["filename"],
                subfolder=output.get("subfolder", ""),
                file_type=output.get("type", "output"),
            )
            relative = Path("outputs") / job.user_id / f"{job.id}.mp4"
            destination = settings.storage_root / relative
            destination.parent.mkdir(parents=True, exist_ok=True)
            destination.write_bytes(video_bytes)
            job.output_path = str(relative)
            job.output_url = await storage.get_url(str(relative))
            job.status = "completed"
            job.stage = "完成"
            job.progress = 1.0
            job.finished_at = datetime.now(UTC)
            await db.commit()
            await publish(job)
        except asyncio.CancelledError:
            raise
        except Exception as exc:
            logger.exception("Video job %s failed", job.id)
            job.status = "failed"
            job.stage = "失败"
            job.error_code = (
                "OUT_OF_MEMORY" if "out of memory" in str(exc).lower() else "GENERATION_FAILED"
            )
            job.error_message = str(exc)[:2000]
            job.finished_at = datetime.now(UTC)
            await db.commit()
            await publish(job)


async def worker_loop() -> None:
    logger.info("Video worker started; GPU concurrency is fixed at 1")
    while True:
        if await redis_client.get("h3:queue:paused"):
            await asyncio.sleep(2)
            continue
        item = await redis_client.blpop(QUEUE_KEY, timeout=0)
        if not item:
            continue
        _, job_id = item
        lock = redis_client.lock(GPU_LOCK_KEY, timeout=7_200, blocking_timeout=30)
        acquired = await lock.acquire()
        if not acquired:
            await redis_client.lpush(QUEUE_KEY, job_id)
            continue
        try:
            await process_job(job_id)
        finally:
            try:
                await lock.release()
            except Exception:
                logger.exception("Failed to release GPU lock")


def main() -> None:
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s %(levelname)s %(name)s %(message)s",
    )
    asyncio.run(worker_loop())


if __name__ == "__main__":
    main()


