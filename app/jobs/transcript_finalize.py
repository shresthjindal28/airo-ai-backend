from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.jobs.base import JobHandler
from app.models.ai_job import AIJob
from app.services.transcript_finalizer import TranscriptFinalizer

logger = get_logger(__name__)


class TranscriptFinalizeJob(JobHandler):

    def __init__(self) -> None:
        self._finalizer = TranscriptFinalizer()

    def run(self, job: AIJob) -> None:
        logger.info(
            "Starting transcript_finalize job job_id=%s consultation_id=%s",
            job.id,
            job.consultation_id,
        )

        db = SessionLocal()
        try:
            self._finalizer.finalize(db, job)
        finally:
            db.close()

        logger.info("Completed transcript_finalize job job_id=%s", job.id)
