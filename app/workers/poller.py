import threading

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.models.enums import AIJobType
from app.repositories.ai_job_repository import AIJobRepository
from app.services.job_service import JobService
from app.workers.executor import JobExecutor
from app.workers.pool_metrics import record_claim, record_idle_poll

logger = get_logger(__name__)


class JobPoller:

    def __init__(
        self,
        executor: JobExecutor,
        shutdown_event: threading.Event,
        *,
        pool_name: str = "default",
        job_types: frozenset[AIJobType] | None = None,
    ) -> None:
        self._executor = executor
        self._shutdown_event = shutdown_event
        self._pool_name = pool_name
        self._job_types = job_types

    def run(self) -> None:
        logger.info(
            "Poller started pool=%s poll_interval=%ss concurrency=%s",
            self._pool_name,
            settings.POLL_INTERVAL_SECONDS,
            self._executor.max_workers,
        )

        while not self._shutdown_event.is_set():
            self._poll_once()

            if self._shutdown_event.wait(timeout=settings.POLL_INTERVAL_SECONDS):
                break

        logger.info("Poller stopped pool=%s", self._pool_name)

    def _poll_once(self) -> None:
        while self._executor.available_slots > 0 and not self._shutdown_event.is_set():
            db = SessionLocal()
            try:
                job = JobService.claim_next_job(db, job_types=self._job_types)
                if job is None:
                    record_idle_poll(self._pool_name)
                    return

                if not self._executor.submit(job):
                    AIJobRepository.requeue_job(
                        db,
                        job,
                        "Worker at capacity; requeued",
                    )
                    return

                record_claim(self._pool_name)
                logger.info(
                    "Claimed job pool=%s job_id=%s type=%s attempt=%s",
                    self._pool_name,
                    job.id,
                    job.job_type,
                    job.attempt_count,
                )
            except Exception:
                logger.exception("Poller error during job claim pool=%s", self._pool_name)
                return
            finally:
                db.close()
