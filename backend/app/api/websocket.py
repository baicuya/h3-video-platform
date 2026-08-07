from __future__ import annotations

import asyncio
import jwt
from fastapi import APIRouter, WebSocket, WebSocketDisconnect

from app.core.config import get_settings
from app.core.database import SessionLocal
from app.core.security import decode_access_token
from app.models.user import User
from app.models.video_job import VideoJob


router = APIRouter()


@router.websocket("/ws/video-jobs/{job_id}")
async def video_job_socket(websocket: WebSocket, job_id: str) -> None:
    token = websocket.cookies.get(get_settings().cookie_name)
    if not token:
        await websocket.close(code=4401)
        return
    try:
        payload = decode_access_token(token)
    except jwt.PyJWTError:
        await websocket.close(code=4401)
        return
    async with SessionLocal() as db:
        user = await db.get(User, str(payload.get("sub")))
        job = await db.get(VideoJob, job_id)
        if (
            user is None
            or not user.is_active
            or user.session_version != int(payload.get("sv", -1))
            or job is None
            or (job.user_id != user.id and user.role != "admin")
        ):
            await websocket.close(code=4403)
            return
    await websocket.accept()
    last_state: tuple[object, ...] | None = None
    try:
        while True:
            async with SessionLocal() as db:
                job = await db.get(VideoJob, job_id)
                if job is None:
                    await websocket.close(code=4404)
                    return
                state = (job.status, job.progress, job.stage, job.error_code, job.output_url)
                if state != last_state:
                    await websocket.send_json(
                        {
                            "id": job.id,
                            "status": job.status,
                            "progress": job.progress,
                            "stage": job.stage,
                            "error_code": job.error_code,
                            "output_url": job.output_url,
                        }
                    )
                    last_state = state
                if job.status in {"completed", "failed", "cancelled"}:
                    return
            await asyncio.sleep(1)
    except WebSocketDisconnect:
        return
