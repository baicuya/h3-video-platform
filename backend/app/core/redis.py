from __future__ import annotations

from redis.asyncio import Redis

from app.core.config import get_settings


redis_client = Redis.from_url(
    get_settings().redis_url,
    decode_responses=True,
    socket_timeout=None,
    socket_connect_timeout=5,
)


async def get_redis() -> Redis:
    return redis_client

