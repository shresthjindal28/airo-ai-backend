from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.jobs.base import JobHandler
from app.models.ai_job import AIJob
from app.services.prescription_generation_service import (
    PrescriptionGenerationService,
    PrescriptionGenerationServiceError,
)

logger = get_logger(__name__)


class PrescriptionGenerationJob(JobHandler):

    def __init__(self) -> None:
        self._service = PrescriptionGenerationService()

    def run(self, job: AIJob) -> None:
        logger.info(
            "Starting prescription_generation job job_id=%s consultation_id=%s",
            job.id,
            job.consultation_id,
        )

        db = SessionLocal()
        try:
            self._service.generate(db, job)
        except PrescriptionGenerationServiceError:
            raise
        finally:
            db.close()

        logger.info("Completed prescription_generation job job_id=%s", job.id)
