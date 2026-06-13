import threading
import uuid
from concurrent.futures import ThreadPoolExecutor
from concurrent.futures import TimeoutError as FuturesTimeoutError

from app.core.config import settings
from app.core.database import SessionLocal
from app.core.logging import get_logger
import app.models  # noqa: F401 — register all ORM tables before job handlers load
from app.jobs.memory_ingestion import MemoryIngestionJob
from app.jobs.memory_reindex import MemoryReindexJob
from app.jobs.patient_briefing_generation import PatientBriefingGenerationJob
from app.jobs.timeline_generation import TimelineGenerationJob
from app.jobs.prescription_generation import PrescriptionGenerationJob
from app.jobs.soap_generation import SOAPGenerationJob
from app.jobs.transcript_finalize import TranscriptFinalizeJob
from app.jobs.transcription import TranscriptionJob
from app.models.ai_job import AIJob
from app.models.enums import AIJobType
from app.repositories.ai_job_repository import AIJobRepository
from app.services.job_service import JobService
from app.services.monitoring_service import MonitoringService
from datetime import UTC, datetime

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
            AIJobType.timeline_generation: TimelineGenerationJob(),
            AIJobType.patient_briefing_generation: PatientBriefingGenerationJob(),
            AIJobType.memory_reindex: MemoryReindexJob(),
        }
    return _HANDLERS


class JobExecutor:

    def __init__(self) -> None:
        self._pool = ThreadPoolExecutor(max_workers=settings.WORKER_CONCURRENCY)
        self._lock = threading.Lock()
        self._active_count = 0
        self._jobs_processed = 0
        self._jobs_failed = 0

    @property
    def active_jobs(self) -> int:
        with self._lock:
            return self._active_count

    @property
    def jobs_processed(self) -> int:
        with self._lock:
            return self._jobs_processed

    @property
    def jobs_failed(self) -> int:
        with self._lock:
            return self._jobs_failed

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
        started_at = datetime.now(UTC)
        job_type_value = "unknown"
        retry_count = 0
        try:
            db = SessionLocal()
            try:
                job = AIJobRepository.get_job_by_id(db, job_id)
                if job is None:
                    logger.error("Job not found after claim job_id=%s", job_id)
                    return

                job_type_value = job.job_type.value
                retry_count = job.attempt_count

                handler = _get_handlers().get(job.job_type)
                if handler is None:
                    error = f"Unknown job type: {job.job_type}"
                    logger.error("Failing job job_id=%s reason=%s", job.id, error)
                    JobService.fail_job(db, job.id, error)
                    self._record_failure(db, job, started_at, retry_count, error)
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
                        self._record_failure(db, job, started_at, retry_count, error)
                        return

                JobService.complete_job(db, job.id)
                self._record_success(db, job, started_at, retry_count)
                logger.info(
                    "Job completed successfully job_id=%s type=%s",
                    job.id,
                    job.job_type,
                )

            except Exception as exc:
                logger.exception("Job failed job_id=%s error=%s", job_id, exc)
                try:
                    job = AIJobRepository.get_job_by_id(db, job_id)
                    JobService.handle_job_failure(db, job_id, str(exc))
                    if job:
                        self._record_failure(db, job, started_at, retry_count, str(exc))
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

    def _record_success(
        self,
        db,
        job: AIJob,
        started_at: datetime,
        retry_count: int,
    ) -> None:
        with self._lock:
            self._jobs_processed += 1
        try:
            MonitoringService.record_job_execution(
                db,
                job_id=job.id,
                job_type=job.job_type.value,
                started_at=started_at,
                status="completed",
                retry_count=retry_count,
            )
        except Exception:
            logger.exception("Failed to record job execution job_id=%s", job.id)

    def _record_failure(
        self,
        db,
        job: AIJob,
        started_at: datetime,
        retry_count: int,
        error: str,
    ) -> None:
        with self._lock:
            self._jobs_failed += 1
        try:
            MonitoringService.record_job_execution(
                db,
                job_id=job.id,
                job_type=job.job_type.value,
                started_at=started_at,
                status="failed",
                retry_count=retry_count,
                error=error,
            )
        except Exception:
            logger.exception("Failed to record job failure job_id=%s", job.id)
