from __future__ import annotations

import os
from collections import defaultdict
from collections.abc import AsyncIterator
from pathlib import Path

import pytest
from httpx import ASGITransport, AsyncClient


TEST_DB = Path("/tmp/h3_video_platform_tests.sqlite3")
os.environ.update(
    {
        "APP_ENV": "test",
        "APP_SECRET_KEY": "test-secret-key-not-for-production",
        "DATABASE_URL": f"sqlite+aiosqlite:///{TEST_DB}",
        "COOKIE_SECURE": "false",
        "STORAGE_ROOT": "/tmp/h3-video-platform-test-data",
        "WORKFLOW_ROOT": "/home/ubuntu/workspace/h3-video-platform/workflows",
        "REF2VA_ENABLED": "true",
    }
)

from sqlalchemy.ext.asyncio import async_sessionmaker, create_async_engine

from app.core.database import Base, get_db
from app.core.redis import get_redis
from app.main import app


class FakeRedis:
    def __init__(self) -> None:
        self.values: dict[str, str] = {}
        self.lists: defaultdict[str, list[str]] = defaultdict(list)

    async def get(self, key: str):
        return self.values.get(key)

    async def set(self, key: str, value: str):
        self.values[key] = str(value)
        return True

    async def incr(self, key: str):
        value = int(self.values.get(key, "0")) + 1
        self.values[key] = str(value)
        return value

    async def expire(self, key: str, _: int):
        return True

    async def delete(self, *keys: str):
        for key in keys:
            self.values.pop(key, None)
            self.lists.pop(key, None)
        return len(keys)

    async def llen(self, key: str):
        return len(self.lists[key])

    async def rpush(self, key: str, *values: str):
        self.lists[key].extend(values)
        return len(self.lists[key])

    async def lpush(self, key: str, *values: str):
        self.lists[key][0:0] = list(values)
        return len(self.lists[key])

    async def lrem(self, key: str, _: int, value: str):
        before = len(self.lists[key])
        self.lists[key] = [item for item in self.lists[key] if item != value]
        return before - len(self.lists[key])

    async def lrange(self, key: str, start: int, end: int):
        stop = None if end == -1 else end + 1
        return self.lists[key][start:stop]

    async def publish(self, _: str, __: str):
        return 1

    async def ping(self):
        return True


test_engine = create_async_engine(
    f"sqlite+aiosqlite:///{TEST_DB}",
    connect_args={"check_same_thread": False},
)
TestSession = async_sessionmaker(test_engine, expire_on_commit=False)
fake_redis = FakeRedis()


async def override_db() -> AsyncIterator:
    async with TestSession() as session:
        yield session


async def override_redis() -> FakeRedis:
    return fake_redis


app.dependency_overrides[get_db] = override_db
app.dependency_overrides[get_redis] = override_redis


@pytest.fixture(autouse=True)
async def reset_state() -> AsyncIterator[None]:
    async with test_engine.begin() as connection:
        await connection.run_sync(Base.metadata.drop_all)
        await connection.run_sync(Base.metadata.create_all)
    fake_redis.values.clear()
    fake_redis.lists.clear()
    yield


@pytest.fixture
async def client() -> AsyncIterator[AsyncClient]:
    async with AsyncClient(
        transport=ASGITransport(app=app),
        base_url="http://testserver",
    ) as test_client:
        yield test_client

