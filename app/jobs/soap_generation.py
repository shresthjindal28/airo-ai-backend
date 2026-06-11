import time

from app.core.logging import get_logger
from app.jobs.base import JobHandler
from app.models.ai_job import AIJob

logger = get_logger(__name__)


class SOAPGenerationJob(JobHandler):

    def run(self, job: AIJob) -> None:
        logger.info(
            "Starting soap_generation job job_id=%s consultation_id=%s",
            job.id,
            job.consultation_id,
        )
        time.sleep(1)
        logger.info("Completed soap_generation job job_id=%s", job.id)
