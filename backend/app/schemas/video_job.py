from __future__ import annotations

from datetime import date, datetime
from typing import Literal

from pydantic import BaseModel, ConfigDict, Field, field_validator


class VideoJobCreate(BaseModel):
    mode: str
    model_variant: Literal["int8"] = "int8"
    generation_profile: Literal["turbo", "fast", "quality"] = "turbo"
    prompt: str = Field(min_length=1, max_length=10_000)
    negative_prompt: str | None = Field(default=None, max_length=5_000)
    duration_seconds: int = 5
    aspect_ratio: str = "16:9"
    resolution: str = "768p"
    seed: int = -1
    flow_shift: float | None = None
    audio_flow_shift: float | None = None
    asset_ids: list[str] = Field(default_factory=list)

    @field_validator("mode")
    @classmethod
    def mode_allowed(cls, value: str) -> str:
        if value not in {"t2v", "i2v", "ref2va"}:
            raise ValueError("非法生成模式")
        return value

    @field_validator("duration_seconds")
    @classmethod
    def duration_allowed(cls, value: int) -> int:
        if value < 1 or value > 15:
            raise ValueError("时长必须在 1～15 秒之间")
        return value

    @field_validator("aspect_ratio")
    @classmethod
    def aspect_allowed(cls, value: str) -> str:
        if value not in {"16:9", "9:16", "1:1", "4:3", "3:4"}:
            raise ValueError("不支持的视频比例")
        return value

    @field_validator("resolution")
    @classmethod
    def resolution_allowed(cls, value: str) -> str:
        if value not in {"480p", "720p", "768p", "1080p"}:
            raise ValueError("不支持的分辨率")
        return value


class VideoJobResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: str
    user_id: str
    parent_job_id: str | None
    mode: str
    status: str
    prompt: str
    negative_prompt: str | None
    duration_seconds: int
    aspect_ratio: str
    resolution: str
    generation_profile: str
    seed: int
    steps: int
    flow_shift: float | None
    audio_flow_shift: float | None
    input_assets: list[str]
    workflow_name: str
    workflow_version: str
    comfy_prompt_id: str | None
    queue_position: int | None
    progress: float | None
    stage: str | None
    output_path: str | None
    output_url: str | None
    thumbnail_path: str | None
    error_code: str | None
    error_message: str | None
    created_at: datetime
    started_at: datetime | None
    finished_at: datetime | None
    updated_at: datetime


class VideoJobQueued(BaseModel):
    id: str
    status: str
    queue_position: int


class VideoJobListResponse(BaseModel):
    items: list[VideoJobResponse]
    total: int
    page: int
    page_size: int


class JobFilters(BaseModel):
    status: str | None = None
    mode: str | None = None
    query: str | None = None
    date_from: date | None = None
    date_to: date | None = None
