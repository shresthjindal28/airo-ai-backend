import threading

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.repositories.ai_job_repository import AIJobRepository
from app.services.job_service import JobService
from app.workers.executor import JobExecutor

logger = get_logger(__name__)


class JobPoller:

    def __init__(self, executor: JobExecutor, shutdown_event: threading.Event) -> None:
        self._executor = executor
        self._shutdown_event = shutdown_event

    def run(self) -> None:
        logger.info(
            "Poller started poll_interval=%ss concurrency=%s",
            settings.POLL_INTERVAL_SECONDS,
            settings.WORKER_CONCURRENCY,
        )

        while not self._shutdown_event.is_set():
            self._poll_once()

            if self._shutdown_event.wait(timeout=settings.POLL_INTERVAL_SECONDS):
                break

        logger.info("Poller stopped")

    def _poll_once(self) -> None:
        while self._executor.available_slots > 0 and not self._shutdown_event.is_set():
            db = SessionLocal()
            try:
                job = JobService.claim_next_job(db)
                if job is None:
                    return

                if not self._executor.submit(job):
                    AIJobRepository.requeue_job(
                        db,
                        job,
                        "Worker at capacity; requeued",
                    )
                    return

                logger.info(
                    "Claimed job job_id=%s type=%s attempt=%s",
                    job.id,
                    job.job_type,
                    job.attempt_count,
                )
            except Exception:
                logger.exception("Poller error during job claim")
                return
            finally:
                db.close()
