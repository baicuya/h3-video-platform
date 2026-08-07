from __future__ import annotations

import logging

from fastapi import FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.middleware.trustedhost import TrustedHostMiddleware
from fastapi.responses import JSONResponse

from app.api.routes import admin_users, assets, auth, system, video_jobs
from app.api.websocket import router as websocket_router
from app.core.config import get_settings


settings = get_settings()
app = FastAPI(
    title="锦宿 AI 视频工作台 API",
    version="1.0.0",
    docs_url="/api/docs" if settings.app_env != "production" else None,
    redoc_url=None,
)
app.add_middleware(
    CORSMiddleware,
    allow_origins=[settings.public_origin],
    allow_credentials=True,
    allow_methods=["GET", "POST", "PATCH", "DELETE", "OPTIONS"],
    allow_headers=["Content-Type", "X-Requested-With"],
)
app.add_middleware(TrustedHostMiddleware, allowed_hosts=settings.trusted_hosts)

for router in (auth.router, admin_users.router, assets.router, video_jobs.router, system.router):
    app.include_router(router, prefix="/api/v1")
app.include_router(websocket_router)


@app.exception_handler(Exception)
async def unhandled_exception(_: Request, exc: Exception) -> JSONResponse:
    logging.getLogger("h3.backend").exception("Unhandled API error", exc_info=exc)
    return JSONResponse(
        status_code=500,
        content={"detail": "服务器内部错误", "error_code": "INTERNAL_ERROR"},
    )
