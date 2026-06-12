from app.core.logging import get_logger
from app.jobs.base import JobHandler
from app.models.ai_job import AIJob

logger = get_logger(__name__)


class MemoryReindexJob(JobHandler):
    """Placeholder for future vector reindex operations at scale."""

    def run(self, job: AIJob) -> None:
        logger.info(
            "memory_reindex noop job_id=%s consultation_id=%s",
            job.id,
            job.consultation_id,
        )
