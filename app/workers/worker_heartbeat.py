import json
import os
import socket
import threading
import uuid
from collections.abc import Callable
from datetime import UTC, datetime

from app.cache.redis_client import get_redis_client, redis_set_json
from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)

WORKER_KEY_PREFIX = "airo:worker:"
STT_STATUS_KEY = "airo:meta:stt:status"
HEARTBEAT_INTERVAL_SECONDS = 15
WORKER_TTL_SECONDS = 45


class WorkerHeartbeat:
    """Publishes worker liveness and stats to Redis."""

    def __init__(
        self,
        *,
        worker_id: str | None = None,
        get_active_jobs: Callable[[], int],
        get_jobs_processed: Callable[[], int],
        get_jobs_failed: Callable[[], int],
    ) -> None:
        self.worker_id = worker_id or f"airo-ai-{uuid.uuid4().hex[:8]}"
        self.hostname = socket.gethostname()
        self.started_at = datetime.now(UTC).isoformat()
        self._get_active_jobs = get_active_jobs
        self._get_jobs_processed = get_jobs_processed
        self._get_jobs_failed = get_jobs_failed
        self._shutdown = threading.Event()
        self._thread: threading.Thread | None = None

    def _redis_key(self) -> str:
        return f"{WORKER_KEY_PREFIX}{self.worker_id}"

    def publish(self) -> None:
        payload = {
            "worker_id": self.worker_id,
            "hostname": self.hostname,
            "started_at": self.started_at,
            "last_heartbeat": datetime.now(UTC).isoformat(),
            "jobs_processed": self._get_jobs_processed(),
            "jobs_failed": self._get_jobs_failed(),
            "active_jobs": self._get_active_jobs(),
            "stt_provider": settings.STT_PROVIDER,
            "sarvam_configured": bool(settings.SARVAM_API_KEY),
        }
        redis_set_json(self._redis_key(), payload, ttl_seconds=WORKER_TTL_SECONDS)
        redis_set_json(
            STT_STATUS_KEY,
            {
                "stt_provider": settings.STT_PROVIDER,
                "sarvam_configured": bool(settings.SARVAM_API_KEY),
                "worker_id": self.worker_id,
                "last_heartbeat": payload["last_heartbeat"],
            },
            ttl_seconds=WORKER_TTL_SECONDS,
        )

    def _loop(self) -> None:
        while not self._shutdown.wait(HEARTBEAT_INTERVAL_SECONDS):
            try:
                self.publish()
            except Exception:
                logger.exception("Worker heartbeat failed worker_id=%s", self.worker_id)

    def start(self) -> None:
        self.publish()
        self._thread = threading.Thread(
            target=self._loop,
            name=f"worker-heartbeat-{self.worker_id}",
            daemon=True,
        )
        self._thread.start()
        logger.info("Worker heartbeat started worker_id=%s", self.worker_id)

    def stop(self) -> None:
        self._shutdown.set()
        if self._thread:
            self._thread.join(timeout=5)
        try:
            get_redis_client().delete(self._redis_key())
        except Exception:
            pass
