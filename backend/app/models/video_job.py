from __future__ import annotations

from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Float, ForeignKey, Integer, JSON, String, Text
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.core.database import Base
from app.models.base import utc_now, uuid_string


class VideoJob(Base):
    __tablename__ = "video_jobs"

    id: Mapped[str] = mapped_column(String(36), primary_key=True, default=uuid_string)
    user_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("users.id", ondelete="RESTRICT"), index=True
    )
    parent_job_id: Mapped[str | None] = mapped_column(
        String(36), ForeignKey("video_jobs.id", ondelete="SET NULL"), nullable=True
    )
    mode: Mapped[str] = mapped_column(String(16), index=True)
    status: Mapped[str] = mapped_column(String(16), default="queued", index=True)
    prompt: Mapped[str] = mapped_column(Text)
    negative_prompt: Mapped[str | None] = mapped_column(Text, nullable=True)
    duration_seconds: Mapped[int] = mapped_column(Integer, default=5)
    aspect_ratio: Mapped[str] = mapped_column(String(16), default="16:9")
    resolution: Mapped[str] = mapped_column(String(16), default="768p")
    seed: Mapped[int] = mapped_column(Integer, default=-1)
    steps: Mapped[int] = mapped_column(Integer, default=20)
    flow_shift: Mapped[float | None] = mapped_column(Float, nullable=True)
    audio_flow_shift: Mapped[float | None] = mapped_column(Float, nullable=True)
    input_assets: Mapped[list[str]] = mapped_column(JSON, default=list)
    workflow_name: Mapped[str] = mapped_column(String(128))
    workflow_version: Mapped[str] = mapped_column(String(64), default="1")
    comfy_prompt_id: Mapped[str | None] = mapped_column(String(128), nullable=True)
    queue_position: Mapped[int | None] = mapped_column(Integer, nullable=True)
    progress: Mapped[float | None] = mapped_column(Float, nullable=True)
    stage: Mapped[str | None] = mapped_column(String(128), nullable=True)
    output_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    output_url: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    thumbnail_path: Mapped[str | None] = mapped_column(String(1024), nullable=True)
    error_code: Mapped[str | None] = mapped_column(String(64), nullable=True)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, index=True
    )
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    updated_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True), default=utc_now, onupdate=utc_now
    )

    user = relationship("User", back_populates="video_jobs")

    def parameters(self) -> dict[str, Any]:
        return {
            "mode": self.mode,
            "prompt": self.prompt,
            "negative_prompt": self.negative_prompt,
            "duration_seconds": self.duration_seconds,
            "aspect_ratio": self.aspect_ratio,
            "resolution": self.resolution,
            "seed": self.seed,
            "steps": self.steps,
            "flow_shift": self.flow_shift,
            "audio_flow_shift": self.audio_flow_shift,
            "asset_ids": self.input_assets,
        }
