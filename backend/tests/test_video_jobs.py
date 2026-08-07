from __future__ import annotations

import pytest

from app.models.asset import Asset

from .conftest import TestSession
from .helpers import create_user, login


@pytest.mark.asyncio
async def test_create_query_cancel_and_invalid_mode(client):
    await create_user(username="creator")
    assert (await login(client, "creator")).status_code == 200
    invalid = await client.post(
        "/api/v1/video-jobs",
        json={"mode": "unknown", "prompt": "bad"},
    )
    assert invalid.status_code == 422

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
    listing = await client.get("/api/v1/video-jobs?status=queued")
    assert listing.status_code == 200
    assert listing.json()["total"] == 1
    cancelled = await client.post(f"/api/v1/video-jobs/{job_id}/cancel")
    assert cancelled.status_code == 200
    assert cancelled.json()["status"] == "cancelled"


@pytest.mark.asyncio
async def test_ref2va_requires_exactly_one_owned_image(client):
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

