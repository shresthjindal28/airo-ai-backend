import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.jobs.memory_ingestion import MemoryIngestionJob
from app.jobs.prescription_generation import PrescriptionGenerationJob
from app.jobs.soap_generation import SOAPGenerationJob
from app.jobs.transcript_finalize import TranscriptFinalizeJob
from app.jobs.transcription import TranscriptionJob
from app.models.ai_job import AIJob
from app.models.enums import AIJobType
from app.repositories.ai_job_repository import AIJobRepository
from app.services.job_service import JobService

logger = get_logger(__name__)

_HANDLERS: dict[AIJobType, object] = {}


def _get_handlers() -> dict[AIJobType, object]:
    global _HANDLERS
    if not _HANDLERS:
        _HANDLERS = {
            AIJobType.transcription: TranscriptionJob(),
            AIJobType.transcript_finalize: TranscriptFinalizeJob(),
            AIJobType.soap_generation: SOAPGenerationJob(),
            AIJobType.prescription_generation: PrescriptionGenerationJob(),
            AIJobType.memory_ingestion: MemoryIngestionJob(),
        }
    return _HANDLERS


class JobExecutor:

    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=settings.WORKER_CONCURRENCY)
        self._lock = threading.Lock()
        self._active_count = 0

    @property
    def available_slots(self) -> int:
        with self._lock:
            return max(0, settings.WORKER_CONCURRENCY - self._active_count)

    def shutdown(self, wait: bool = True) -> None:
        self._pool.shutdown(wait=wait)

    def submit(self, job: AIJob) -> bool:
        with self._lock:
            if self._active_count >= settings.WORKER_CONCURRENCY:
                return False
            self._active_count += 1

        self._pool.submit(self._process_job, job.id)
        return True

    def _process_job(self, job_id: uuid.UUID) -> None:
        try:
            db = SessionLocal()
            try:
                job = AIJobRepository.get_job_by_id(db, job_id)
                if job is None:
                    logger.error("Job not found after claim job_id=%s", job_id)
                    return

                handler = _get_handlers().get(job.job_type)
                if handler is None:
                    error = f"Unknown job type: {job.job_type}"
                    logger.error("Failing job job_id=%s reason=%s", job.id, error)
                    JobService.fail_job(db, job.id, error)
                    return

                with ThreadPoolExecutor(max_workers=1) as handler_pool:
                    future = handler_pool.submit(handler.run, job)
                    try:
                        future.result(timeout=settings.JOB_TIMEOUT_SECONDS)
                    except FuturesTimeoutError:
                        error = (
                            f"Job timed out after {settings.JOB_TIMEOUT_SECONDS}s"
                        )
                        logger.error("Job timed out job_id=%s", job.id)
                        JobService.handle_job_failure(db, job.id, error)
                        return

                JobService.complete_job(db, job.id)
                logger.info(
                    "Job completed successfully job_id=%s type=%s",
                    job.id,
                    job.job_type,
                )

            except Exception as exc:
                logger.exception("Job failed job_id=%s error=%s", job_id, exc)
                try:
                    JobService.handle_job_failure(db, job_id, str(exc))
                except Exception:
                    logger.exception(
                        "Failed to record job failure job_id=%s",
                        job_id,
                    )
            finally:
                db.close()
        finally:
            with self._lock:
                self._active_count -= 1
