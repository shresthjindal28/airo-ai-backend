import json
from functools import lru_cache
from typing import Any

import redis

from app.core.config import settings


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.Redis.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        socket_connect_timeout=2,
        socket_timeout=2,
    )


def redis_set_json(key: str, value: Any, *, ttl_seconds: int) -> bool:
    try:
        get_redis_client().setex(key, ttl_seconds, json.dumps(value, default=str))
        return True
    except (redis.RedisError, TypeError):
        return False


def redis_delete_pattern(prefix: str) -> int:
    try:
        client = get_redis_client()
        deleted = 0
        for key in client.scan_iter(match=f"{prefix}*"):
            deleted += int(client.delete(key) or 0)
        return deleted
    except redis.RedisError:
        return 0


def redis_incr(key: str) -> int:
    try:
        return int(get_redis_client().incr(key))
    except redis.RedisError:
        return 0
