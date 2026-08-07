from __future__ import annotations

from datetime import datetime

from pydantic import BaseModel, ConfigDict


class AssetResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    kind: str
    original_name: str
    mime_type: str
    size_bytes: int
    created_at: datetime


class AssetListResponse(BaseModel):
    items: list[AssetResponse]
    total: int
