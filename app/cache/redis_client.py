import json
import threading
from functools import lru_cache
from typing import Any

import redis

from app.core.config import settings

_pool_lock = threading.Lock()
_redis_pool: redis.ConnectionPool | None = None


def _build_pool() -> redis.ConnectionPool:
    return redis.ConnectionPool.from_url(
        settings.REDIS_URL,
        decode_responses=True,
        max_connections=100,
        socket_connect_timeout=2,
        socket_timeout=2,
        socket_keepalive=True,
        health_check_interval=0,
        retry_on_timeout=True,
    )


def get_redis_pool() -> redis.ConnectionPool:
    global _redis_pool
    if _redis_pool is None:
        with _pool_lock:
            if _redis_pool is None:
                _redis_pool = _build_pool()
    return _redis_pool


@lru_cache
def get_redis_client() -> redis.Redis:
    return redis.Redis(connection_pool=get_redis_pool())


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
