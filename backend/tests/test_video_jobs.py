from __future__ import annotations

import pytest
from sqlalchemy import select

from app.api.routes import video_jobs as video_jobs_route
from app.models.asset import Asset
from app.models.video_job import VideoJob

from .conftest import TestSession, fake_redis
from .helpers import create_user, login


async def create_assets(user_id: str, specs: list[tuple[str, str]]) -> list[str]:
    async with TestSession() as db:
        assets = [
            Asset(
                user_id=user_id,
                kind=kind,
                original_name=name,
                storage_path=f"uploads/{user_id}/{index}-{name}",
                mime_type={
                    "image": "image/png",
                    "video": "video/mp4",
                    "audio": "audio/wav",
                }[kind],
                size_bytes=128,
            )
            for index, (kind, name) in enumerate(specs)
        ]
        db.add_all(assets)
        await db.commit()
        for asset in assets:
            await db.refresh(asset)
        return [asset.id for asset in assets]


@pytest.mark.asyncio
async def test_job_is_committed_before_it_is_published_to_queue(client, monkeypatch):
    await create_user(username="queue-order")
    assert (await login(client, "queue-order")).status_code == 200
    original_rpush = fake_redis.rpush

    async def assert_committed_before_push(key: str, *values: str):
        async with TestSession() as db:
            job = await db.get(VideoJob, values[0])
            assert job is not None
            assert job.status == "queued"
        return await original_rpush(key, *values)

    monkeypatch.setattr(fake_redis, "rpush", assert_committed_before_push)
    response = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "t2v", "prompt": "Queue safely", "resolution": "480p"},
    )

    assert response.status_code == 201
    assert fake_redis.lists["h3:video_jobs"] == [response.json()["id"]]


@pytest.mark.asyncio
async def test_queue_publish_failure_marks_job_failed(client, monkeypatch):
    user = await create_user(username="queue-failure")
    assert (await login(client, "queue-failure")).status_code == 200

    async def fail_rpush(_key: str, *_values: str):
        raise ConnectionError("redis unavailable")

    monkeypatch.setattr(fake_redis, "rpush", fail_rpush)
    response = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "t2v", "prompt": "Fail clearly", "resolution": "480p"},
    )

    assert response.status_code == 503
    async with TestSession() as db:
        job = await db.scalar(select(VideoJob).where(VideoJob.user_id == user.id))
        assert job is not None
        assert job.status == "failed"
        assert job.error_code == "QUEUE_UNAVAILABLE"


@pytest.mark.asyncio
async def test_create_query_cancel_and_invalid_mode(client):
    await create_user(username="creator")
    assert (await login(client, "creator")).status_code == 200
    invalid = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "unknown", "prompt": "bad"},
    )
    assert invalid.status_code == 422
    removed_variant = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "t2v", "model_variant": "bf16", "prompt": "bad"},
    )
    assert removed_variant.status_code == 422

    created = await client.post(
        "/api/v1/video-jobs",
        json={
            "mode": "t2v",
            "prompt": "A calm lake",
            "duration_seconds": 5,
            "aspect_ratio": "16:9",
            "resolution": "480p",
            "seed": -1,
        },
    )
    assert created.status_code == 201
    job_id = created.json()["id"]
    assert created.json()["queue_position"] == 1

    detail = await client.get(f"/api/v1/video-jobs/{job_id}")
    assert detail.status_code == 200
    assert detail.json()["prompt"] == "A calm lake"
    assert detail.json()["workflow_name"] == "h3_t2v_int8.json"
    listing = await client.get("/api/v1/video-jobs?status=queued")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    cancelled = await client.post(f"/api/v1/video-jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_ref2va_accepts_an_owned_image(client):
    user = await create_user(username="reference")
    assert (await login(client, "reference")).status_code == 200
    missing = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "ref2va", "prompt": "Use <Picture 1> as reference"},
    )
    assert missing.status_code == 422

    async with TestSession() as db:
        asset = Asset(
            user_id=user.id,
            kind="image",
            original_name="reference.png",
            storage_path=f"uploads/{user.id}/reference.png",
            mime_type="image/png",
            size_bytes=128,
        )
        db.add(asset)
        await db.commit()
        await db.refresh(asset)
        asset_id = asset.id

    created = await client.post(
        "/api/v1/video-jobs",
        json={
            "mode": "ref2va",
            "prompt": "Use <Picture 1> as the exact visual reference",
            "asset_ids": [asset_id],
            "resolution": "480p",
        },
    )
    assert created.status_code == 201
    detail = await client.get(f"/api/v1/video-jobs/{created.json()['id']}")
    assert detail.json()["workflow_name"] == "h3_ref2va_int8.json"


@pytest.mark.asyncio
async def test_ref2va_mixed_assets_and_limits(client, monkeypatch):
    user = await create_user(username="mixed-reference")
    assert (await login(client, "mixed-reference")).status_code == 200

    async def fake_duration(path):
        name = str(path)
        return 8.0 if name.endswith(".mp4") or "long-" in name else 4.5

    monkeypatch.setattr(video_jobs_route, "media_duration_seconds", fake_duration)
    asset_ids = await create_assets(
        user.id,
        [
            ("image", "person.png"),
            ("video", "motion.mp4"),
            ("audio", "voice.wav"),
        ],
    )
    created = await client.post(
        "/api/v1/video-jobs",
        json={
            "mode": "ref2va",
            "prompt": "Use <Picture 1>, <Video 1> and <Audio 1>",
            "asset_ids": asset_ids,
            "resolution": "480p",
        },
    )
    assert created.status_code == 201
    detail = await client.get(f"/api/v1/video-jobs/{created.json()['id']}")
    assert detail.json()["input_assets"] == asset_ids

    audio_only = await create_assets(user.id, [("audio", "only.wav")])
    rejected_audio_only = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "ref2va", "prompt": "Audio only", "asset_ids": audio_only},
    )
    assert rejected_audio_only.status_code == 422
    assert "不能只上传音频" in rejected_audio_only.json()["detail"]

    too_many_images = await create_assets(
        user.id,
        [("image", f"image-{index}.png") for index in range(10)],
    )
    rejected_images = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "ref2va", "prompt": "Too many", "asset_ids": too_many_images},
    )
    assert rejected_images.status_code == 422
    assert "最多上传 9 张" in rejected_images.json()["detail"]

    too_long = await create_assets(
        user.id,
        [("image", "anchor.png"), ("video", "one.mp4"), ("video", "two.mp4")],
    )
    rejected_duration = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "ref2va", "prompt": "Too long", "asset_ids": too_long},
    )
    assert rejected_duration.status_code == 422
    assert "视频总时长最多 15 秒" in rejected_duration.json()["detail"]

    too_long_audio = await create_assets(
        user.id,
        [("image", "speaker.png"), ("audio", "long-one.wav"), ("audio", "long-two.wav")],
    )
    rejected_audio_duration = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "ref2va", "prompt": "Too long", "asset_ids": too_long_audio},
    )
    assert rejected_audio_duration.status_code == 422
    assert "音频总时长最多 15 秒" in rejected_audio_duration.json()["detail"]

    too_many_total = await create_assets(
        user.id,
        [
            *[("image", f"total-image-{index}.png") for index in range(7)],
            *[("video", f"total-video-{index}.mp4") for index in range(3)],
            *[("audio", f"total-audio-{index}.wav") for index in range(3)],
        ],
    )
    rejected_total = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "ref2va", "prompt": "Too many total", "asset_ids": too_many_total},
    )
    assert rejected_total.status_code == 422
    assert "总数最多 12 个" in rejected_total.json()["detail"]


@pytest.mark.asyncio
async def test_fl2va_accepts_first_and_last_frame(client):
    user = await create_user(username="first-last")
    assert (await login(client, "first-last")).status_code == 200
    asset_ids = await create_assets(
        user.id,
        [("image", "first.png"), ("image", "last.png")],
    )
    created = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "i2v", "prompt": "First to last", "asset_ids": asset_ids},
    )
    assert created.status_code == 201
    detail = await client.get(f"/api/v1/video-jobs/{created.json()['id']}")
    assert detail.json()["input_assets"] == asset_ids
    assert detail.json()["workflow_name"] == "h3_i2v_int8.json"


@pytest.mark.asyncio
async def test_jobs_are_private(client):
    await create_user(username="owner")
    await create_user(username="other")
    assert (await login(client, "owner")).status_code == 200
    created = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "t2v", "prompt": "private"},
    )
    job_id = created.json()["id"]
    client.cookies.clear()
    assert (await login(client, "other")).status_code == 200
    assert (await client.get(f"/api/v1/video-jobs/{job_id}")).status_code == 404
