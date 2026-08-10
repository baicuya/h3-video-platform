from __future__ import annotations

import pytest

from app.api.routes import system
from app.models.video_job import VideoJob

from .conftest import TestSession, fake_redis
from .helpers import create_user, login


class FakeNvidiaProcess:
    async def communicate(self):
        return b"NVIDIA Test GPU, 1024, 24576, 42, 58\n", b""


@pytest.mark.asyncio
async def test_admin_system_status_includes_host_resources(client, monkeypatch):
    await create_user(username="admin", role="admin")
    assert (await login(client, "admin")).status_code == 200

    async def fake_subprocess(*_args, **_kwargs):
        return FakeNvidiaProcess()

    async def fake_resources():
        return {
            "cpu": {"utilization_percent": 25.5, "logical_cores": 8},
            "memory": {
                "total": 16_000,
                "used": 10_000,
                "available": 6_000,
                "utilization_percent": 62.5,
            },
            "disk": {
                "total": 100_000,
                "used": 40_000,
                "free": 60_000,
                "utilization_percent": 40.0,
            },
        }

    monkeypatch.setattr(system.asyncio, "create_subprocess_exec", fake_subprocess)
    monkeypatch.setattr(system, "_system_resources", fake_resources)

    response = await client.get("/api/v1/system/gpu")

    assert response.status_code == 200
    body = response.json()
    assert body["cpu"] == {"utilization_percent": 25.5, "logical_cores": 8}
    assert body["memory"]["utilization_percent"] == 62.5
    assert body["disk"]["utilization_percent"] == 40.0
    assert body["name"] == "NVIDIA Test GPU"


@pytest.mark.asyncio
async def test_normal_user_cannot_access_system_status(client):
    await create_user(username="normal")
    assert (await login(client, "normal")).status_code == 200

    response = await client.get("/api/v1/system/gpu")

    assert response.status_code == 403


@pytest.mark.asyncio
async def test_admin_queue_includes_job_owner_time_and_dimensions(client):
    admin = await create_user(username="admin", role="admin")
    owner = await create_user(username="jx_001")
    assert (await login(client, "admin")).status_code == 200

    async with TestSession() as db:
        running = VideoJob(
            user_id=admin.id,
            mode="i2v",
            status="running",
            prompt="running",
            aspect_ratio="9:16",
            resolution="480p",
            duration_seconds=5,
            workflow_name="h3_i2v_int8.json",
        )
        queued = VideoJob(
            user_id=owner.id,
            mode="t2v",
            status="queued",
            prompt="queued",
            aspect_ratio="16:9",
            resolution="720p",
            duration_seconds=15,
            workflow_name="h3_t2v_int8.json",
        )
        db.add_all([running, queued])
        await db.commit()
        await db.refresh(running)
        await db.refresh(queued)

    await fake_redis.rpush("h3:video_jobs", queued.id)
    response = await client.get("/api/v1/system/queue")

    assert response.status_code == 200
    body = response.json()
    assert body["length"] == 1
    assert [job["id"] for job in body["jobs"]] == [running.id, queued.id]
    assert body["jobs"][0]["queue_position"] is None
    assert body["jobs"][0]["queue_state"] == "running"
    assert body["jobs"][0]["user_role"] == "admin"
    queued_body = body["jobs"][1]
    assert queued_body["queue_position"] == 1
    assert queued_body["queue_state"] == "waiting"
    assert queued_body["username"] == "jx_001"
    assert queued_body["display_name"] == "Jx_001"
    assert queued_body["user_role"] == "user"
    assert queued_body["aspect_ratio"] == "16:9"
    assert queued_body["resolution"] == "720p"
    assert (queued_body["width"], queued_body["height"]) == (1280, 736)
    assert queued_body["duration_seconds"] == 15
    assert queued_body["created_at"]

    await fake_redis.delete("h3:video_jobs")
    recovered_view = await client.get("/api/v1/system/queue")
    orphan = next(job for job in recovered_view.json()["jobs"] if job["id"] == queued.id)
    assert recovered_view.json()["length"] == 1
    assert orphan["queue_position"] is None
    assert orphan["queue_state"] == "recovering"
