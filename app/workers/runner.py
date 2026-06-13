import signal
import sys
import threading

from app.core.config import settings
from app.core.logging import get_logger, setup_logging
import app.models  # noqa: F401 — register ORM metadata (Doctor/Patient stubs for FKs)
from app.workers.executor import JobExecutor
from app.workers.poller import JobPoller
from app.workers.worker_heartbeat import WorkerHeartbeat

logger = get_logger(__name__)


def main() -> None:
    setup_logging()

    if not settings.WORKER_ENABLED:
        logger.error("WORKER_ENABLED is false; exiting")
        sys.exit(1)

    shutdown_event = threading.Event()
    executor = JobExecutor()
    poller = JobPoller(executor, shutdown_event)
    heartbeat = WorkerHeartbeat(
        get_active_jobs=lambda: executor.active_jobs,
        get_jobs_processed=lambda: executor.jobs_processed,
        get_jobs_failed=lambda: executor.jobs_failed,
    )

    def handle_shutdown(signum: int, _frame: object) -> None:
        signal_name = signal.Signals(signum).name
        logger.info("Shutdown signal received signal=%s", signal_name)
        shutdown_event.set()

    signal.signal(signal.SIGINT, handle_shutdown)
    signal.signal(signal.SIGTERM, handle_shutdown)

    logger.info("airo-ai worker starting")

    if settings.EMBEDDING_PROVIDER.lower() == "local":
        from app.providers.embeddings.local_provider import preload_embedding_model

        preload_embedding_model()

    try:
        heartbeat.start()
        poller.run()
    finally:
        heartbeat.stop()
        logger.info("Shutting down executor")
        executor.shutdown(wait=True)
        logger.info("airo-ai worker stopped")


if __name__ == "__main__":
    main()
