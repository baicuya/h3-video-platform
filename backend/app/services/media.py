from __future__ import annotations

import asyncio
from pathlib import Path


async def media_duration_seconds(path: Path) -> float:
    try:
        process = await asyncio.create_subprocess_exec(
            "ffprobe",
            "-v",
            "error",
            "-show_entries",
            "format=duration",
            "-of",
            "default=noprint_wrappers=1:nokey=1",
            str(path),
            stdout=asyncio.subprocess.PIPE,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise ValueError("无法启动 ffprobe 读取素材时长") from exc
    try:
        stdout, _ = await asyncio.wait_for(process.communicate(), timeout=30)
    except TimeoutError as exc:
        process.kill()
        await process.communicate()
        raise ValueError("读取素材时长超时") from exc
    try:
        duration = float(stdout.decode().strip())
    except ValueError as exc:
        raise ValueError("无法读取素材时长") from exc
    if process.returncode != 0 or duration <= 0:
        raise ValueError("无法读取素材时长")
    return duration


async def trim_video_tail(
    source: Path,
    destination: Path,
    duration_seconds: int,
    *,
    source_duration: float | None = None,
) -> float:
    duration = source_duration or await media_duration_seconds(source)
    start = max(0.0, duration - duration_seconds)
    destination.parent.mkdir(parents=True, exist_ok=True)
    try:
        process = await asyncio.create_subprocess_exec(
            "ffmpeg",
            "-hide_banner",
            "-loglevel",
            "error",
            "-y",
            "-ss",
            f"{start:.6f}",
            "-i",
            str(source),
            "-t",
            str(duration_seconds),
            "-map",
            "0:v:0",
            "-map",
            "0:a?",
            "-c:v",
            "libx264",
            "-preset",
            "medium",
            "-crf",
            "18",
            "-pix_fmt",
            "yuv420p",
            "-c:a",
            "aac",
            "-b:a",
            "192k",
            "-movflags",
            "+faststart",
            str(destination),
            stdout=asyncio.subprocess.DEVNULL,
            stderr=asyncio.subprocess.PIPE,
        )
    except OSError as exc:
        raise ValueError("无法启动 ffmpeg 裁剪视频") from exc
    try:
        _, stderr = await asyncio.wait_for(process.communicate(), timeout=600)
    except TimeoutError as exc:
        process.kill()
        await process.communicate()
        destination.unlink(missing_ok=True)
        raise ValueError("视频裁剪超时") from exc
    if process.returncode != 0 or not destination.is_file() or destination.stat().st_size == 0:
        destination.unlink(missing_ok=True)
        detail = stderr.decode(errors="replace").strip().splitlines()
        message = detail[-1][:300] if detail else "未知错误"
        raise ValueError(f"视频裁剪失败：{message}")
    try:
        return await media_duration_seconds(destination)
    except ValueError:
        destination.unlink(missing_ok=True)
        raise
