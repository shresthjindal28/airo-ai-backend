"""In-process worker pool metrics and starvation detection."""

from __future__ import annotations

import threading
import time
from collections import defaultdict

_lock = threading.Lock()
_pool_claimed: dict[str, int] = defaultdict(int)
_pool_idle_polls: dict[str, int] = defaultdict(int)
_pool_last_claim_at: dict[str, float] = {}
_starvation_threshold_polls = 10


def record_claim(pool_name: str) -> None:
    with _lock:
        _pool_claimed[pool_name] += 1
        _pool_last_claim_at[pool_name] = time.time()
        _pool_idle_polls[pool_name] = 0


def record_idle_poll(pool_name: str) -> None:
    with _lock:
        _pool_idle_polls[pool_name] += 1


def snapshot() -> dict:
    with _lock:
        pools = {}
        for pool_name in set(_pool_claimed) | set(_pool_idle_polls):
            idle = _pool_idle_polls.get(pool_name, 0)
            pools[pool_name] = {
                "jobs_claimed": _pool_claimed.get(pool_name, 0),
                "idle_polls": idle,
                "starvation_suspected": idle >= _starvation_threshold_polls,
                "last_claim_epoch": _pool_last_claim_at.get(pool_name),
            }
        return {
            "pools": pools,
            "scaling_guidance": _scaling_guidance(pools),
        }


def _scaling_guidance(pools: dict) -> list[str]:
    guidance: list[str] = []
    for name, stats in pools.items():
        if stats.get("starvation_suspected"):
            guidance.append(
                f"Increase {name} pool concurrency — {stats['idle_polls']} idle polls without claims"
            )
        if stats.get("jobs_claimed", 0) > 1000:
            guidance.append(f"{name} pool high throughput; consider horizontal scale-out")
    if not guidance:
        guidance.append("Pool utilization balanced; maintain current concurrency")
    return guidance
