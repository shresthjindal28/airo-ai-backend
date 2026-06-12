import uuid

from app.core.database import SessionLocal
from app.core.logging import get_logger
from app.jobs.base import JobHandler
from app.models.ai_job import AIJob
from app.services.timeline_generation_service import TimelineGenerationService

logger = get_logger(__name__)


class TimelineGenerationJob(JobHandler):

    def __init__(self) -> None:
        self._service = TimelineGenerationService()

    def run(self, job: AIJob) -> None:
        metadata = job.metadata_ or {}
        patient_id_raw = metadata.get("patient_id")
        if not patient_id_raw:
            raise ValueError("timeline_generation requires patient_id metadata")

        patient_id = uuid.UUID(str(patient_id_raw))
        db = SessionLocal()
        try:
            timeline = self._service.generate(db, patient_id)
            logger.info(
                "timeline_generation completed job_id=%s patient_id=%s events=%s",
                job.id,
                patient_id,
                len(timeline.get("events") or []),
            )
        finally:
            db.close()
