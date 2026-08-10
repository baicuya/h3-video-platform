from __future__ import annotations

from pathlib import Path
from typing import Annotated

from fastapi import APIRouter, Depends, File, HTTPException, UploadFile, status
from fastapi.responses import FileResponse
from sqlalchemy import func, select
from sqlalchemy.ext.asyncio import AsyncSession

from app.api.dependencies import require_password_changed
from app.core.config import get_settings
from app.core.database import get_db
from app.models.asset import Asset
from app.models.user import User
from app.schemas.asset import AssetListResponse, AssetResponse
from app.services.storage import LocalStorageProvider


router = APIRouter(prefix="/assets", tags=["assets"])
settings = get_settings()
storage = LocalStorageProvider(settings.storage_root)

ALLOWED = {
    "images": {
        "kind": "image",
        "extensions": {".jpg", ".jpeg", ".png", ".webp"},
        "mimes": {"image/jpeg", "image/png", "image/webp"},
        "max_mb": settings.max_image_mb,
    },
    "videos": {
        "kind": "video",
        "extensions": {".mp4", ".mov", ".webm"},
        "mimes": {"video/mp4", "video/quicktime", "video/webm"},
        "max_mb": settings.max_video_mb,
    },
    "audio": {
        "kind": "audio",
        "extensions": {".wav", ".mp3", ".m4a", ".flac"},
        "mimes": {
            "audio/wav",
            "audio/x-wav",
            "audio/mpeg",
            "audio/mp4",
            "audio/flac",
        },
        "max_mb": settings.max_audio_mb,
    },
}


async def save_asset(
    category: str,
    upload: UploadFile,
    user: User,
    db: AsyncSession,
) -> Asset:
    policy = ALLOWED[category]
    extension = Path(upload.filename or "").suffix.lower()
    if extension not in policy["extensions"] or upload.content_type not in policy["mimes"]:
        raise HTTPException(status_code=415, detail="不支持的文件类型")
    try:
        storage_path, size_bytes = await storage.save_upload(
            upload,
            kind=str(policy["kind"]),
            extension=extension,
            max_bytes=int(policy["max_mb"]) * 1024 * 1024,
        )
    except ValueError as exc:
        raise HTTPException(status_code=413, detail=str(exc)) from exc
    asset = Asset(
        user_id=user.id,
        kind=str(policy["kind"]),
        original_name=upload.filename or "unnamed",
        storage_path=storage_path,
        mime_type=upload.content_type or "application/octet-stream",
        size_bytes=size_bytes,
    )
    db.add(asset)
    await db.commit()
    await db.refresh(asset)
    return asset


@router.post("/images", response_model=AssetResponse, status_code=201)
async def upload_image(
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> Asset:
    return await save_asset("images", file, user, db)


@router.post("/videos", response_model=AssetResponse, status_code=201)
async def upload_video(
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> Asset:
    return await save_asset("videos", file, user, db)


@router.post("/audio", response_model=AssetResponse, status_code=201)
async def upload_audio(
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
    file: UploadFile = File(...),
) -> Asset:
    return await save_asset("audio", file, user, db)


@router.get("", response_model=AssetListResponse)
async def list_assets(
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> AssetListResponse:
    assets = (
        await db.scalars(
            select(Asset).where(Asset.user_id == user.id).order_by(Asset.created_at.desc())
        )
    ).all()
    return AssetListResponse(items=list(assets), total=len(assets))


@router.get("/{asset_id}/content", response_class=FileResponse)
async def preview_asset(
    asset_id: str,
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> FileResponse:
    asset = await db.get(Asset, asset_id)
    if asset is None or (asset.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="素材不存在")
    path = storage.absolute_path(asset.storage_path)
    if not path.is_file():
        raise HTTPException(status_code=404, detail="素材文件不存在")
    return FileResponse(
        path,
        media_type=asset.mime_type,
        filename=asset.original_name,
        content_disposition_type="inline",
        headers={"Cache-Control": "private, max-age=3600"},
    )


@router.delete("/{asset_id}", status_code=204)
async def delete_asset(
    asset_id: str,
    user: Annotated[User, Depends(require_password_changed)],
    db: Annotated[AsyncSession, Depends(get_db)],
) -> None:
    asset = await db.get(Asset, asset_id)
    if asset is None or (asset.user_id != user.id and user.role != "admin"):
        raise HTTPException(status_code=404, detail="素材不存在")
    await storage.delete(asset.storage_path)
    await db.delete(asset)
    await db.commit()
