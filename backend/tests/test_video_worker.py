from __future__ import annotations

from datetime import UTC, datetime, timedelta

import pytest

from app.models.video_job import VideoJob
from app.workers.video_worker import recover_orphaned_jobs

from .conftest import TestSession, fake_redis
from .helpers import create_user


@pytest.mark.asyncio
async def test_recover_orphaned_queued_jobs_is_idempotent():
    user = await create_user(username="orphan-owner")
    async with TestSession() as db:
        job = VideoJob(
            user_id=user.id,
            mode="t2v",
            status="queued",
            prompt="Recover me",
            workflow_name="h3_t2v_int8.json",
            created_at=datetime.now(UTC) - timedelta(minutes=1),
        )
        db.add(job)
        await db.commit()
        await db.refresh(job)

    recovered = await recover_orphaned_jobs(
        db_factory=TestSession,
        redis=fake_redis,
        grace_seconds=0,
    )
    recovered_again = await recover_orphaned_jobs(
        db_factory=TestSession,
        redis=fake_redis,
        grace_seconds=0,
    )

    assert recovered == 1
    assert recovered_again == 0
    assert fake_redis.lists["h3:video_jobs"] == [job.id]
