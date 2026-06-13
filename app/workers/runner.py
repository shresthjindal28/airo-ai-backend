import signal
import sys
import threading

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
import app.models  # noqa: F401 — register ORM metadata (Doctor/Patient stubs for FKs)
from app.workers.executor import JobExecutor
from app.workers.poller import JobPoller
from app.workers.pool_config import POOL_SPECS
from app.workers.worker_heartbeat import WorkerHeartbeat

logger = get_logger(__name__)


def _pool_concurrency(total: int, pool_count: int) -> int:
    base = max(1, total // pool_count)
    remainder = max(0, total - base * pool_count)
    return base + (1 if remainder > 0 else 0)


def main() -> None:
    setup_logging()

    if not settings.WORKER_ENABLED:
        logger.error("WORKER_ENABLED is false; exiting")
        sys.exit(1)

    shutdown_event = threading.Event()
    total_concurrency = max(settings.WORKER_CONCURRENCY, len(POOL_SPECS))
    per_pool = _pool_concurrency(total_concurrency, len(POOL_SPECS))

    executors: list[JobExecutor] = []
    pollers: list[JobPoller] = []
    threads: list[threading.Thread] = []

    aggregate_processed = lambda: sum(e.jobs_processed for e in executors)
    aggregate_failed = lambda: sum(e.jobs_failed for e in executors)
    aggregate_active = lambda: sum(e.active_jobs for e in executors)

    for pool_name, job_types in POOL_SPECS:
        executor = JobExecutor(max_workers=per_pool)
        poller = JobPoller(
            executor,
            shutdown_event,
            pool_name=pool_name,
            job_types=job_types,
        )
        executors.append(executor)
        pollers.append(poller)
        thread = threading.Thread(
            target=poller.run,
            name=f"poller-{pool_name}",
            daemon=True,
        )
        threads.append(thread)

    heartbeat = WorkerHeartbeat(
        get_active_jobs=aggregate_active,
        get_jobs_processed=aggregate_processed,
        get_jobs_failed=aggregate_failed,
    )

    def handle_shutdown(signum: int, _frame: object) -> None:
        signal_name = signal.Signals(signum).name
        logger.info("Shutdown signal received signal=%s", signal_name)
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info(
        "airo-ai worker starting pools=%s total_concurrency=%s per_pool=%s",
        len(POOL_SPECS),
        total_concurrency,
        per_pool,
    )

    if settings.EMBEDDING_PROVIDER.lower() == "local":
        from app.providers.embeddings.local_provider import preload_embedding_model

        preload_embedding_model()

    try:
        heartbeat.start()
        for thread in threads:
            thread.start()
        for thread in threads:
            thread.join()
    finally:
        heartbeat.stop()
        for executor in executors:
            logger.info("Shutting down executor")
            executor.shutdown(wait=True)
        logger.info("airo-ai worker stopped")


if __name__ == "__main__":
    main()
