from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.jobs.base import JobHandler
from app.models.ai_job import AIJob
from app.services.memory_ingestion_service import MemoryIngestionService

logger = get_logger(__name__)


class MemoryIngestionJob(JobHandler):

    def __init__(self) -> None:
        self._service = MemoryIngestionService()

    def run(self, job: AIJob) -> None:
        logger.info(
            "Starting memory_ingestion job job_id=%s consultation_id=%s",
            job.id,
            job.consultation_id,
        )

        db = SessionLocal()
        try:
            document_id = self._service.ingest(db, job)
            logger.info(
                "Completed memory_ingestion job job_id=%s document_id=%s",
                job.id,
                document_id,
            )
        finally:
            db.close()
