import uuid

from sqlalchemy.orm import Session

from app.core.config import settings
from app.models.ai_job import AIJob
from app.models.enums import AIJobStatus, AIJobType
from app.repositories.ai_job_repository import AIJobRepository


class JobNotFoundError(Exception):
    pass


class InvalidJobStateError(Exception):
    pass


class JobService:

    @staticmethod
    def claim_next_job(
        db: Session,
        *,
        job_types: frozenset[AIJobType] | None = None,
    ) -> AIJob | None:
        return AIJobRepository.claim_job(db, job_types=job_types)

    @staticmethod
    def complete_job(db: Session, job_id: uuid.UUID) -> AIJob:
        job = AIJobRepository.get_job_by_id(db, job_id)

        if not job:
            raise JobNotFoundError(f"Job not found: {job_id}")

        if job.status != AIJobStatus.processing:
            raise InvalidJobStateError(
                f"Only processing jobs can be completed (current: {job.status})"
            )

        return AIJobRepository.mark_completed(db, job)

    @staticmethod
    def fail_job(
        db: Session,
        job_id: uuid.UUID,
        error_message: str,
    ) -> AIJob:
        job = AIJobRepository.get_job_by_id(db, job_id)

        if not job:
            raise JobNotFoundError(f"Job not found: {job_id}")

        if job.status != AIJobStatus.processing:
            raise InvalidJobStateError(
                f"Only processing jobs can fail (current: {job.status})"
            )

        return AIJobRepository.mark_failed(db, job, error_message)

    @staticmethod
    def retry_job(db: Session, job_id: uuid.UUID) -> AIJob:
        job = AIJobRepository.get_job_by_id(db, job_id)

        if not job:
            raise JobNotFoundError(f"Job not found: {job_id}")

        if job.status != AIJobStatus.failed:
            raise InvalidJobStateError(
                f"Only failed jobs can be retried (current: {job.status})"
            )

        job.status = AIJobStatus.queued
        job.started_at = None
        job.completed_at = None
        job.error_message = None
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def handle_job_failure(
        db: Session,
        job_id: uuid.UUID,
        error_message: str,
    ) -> AIJob:
        job = AIJobRepository.get_job_by_id(db, job_id)

        if not job:
            raise JobNotFoundError(f"Job not found: {job_id}")

        if job.attempt_count >= settings.MAX_JOB_ATTEMPTS:
            return AIJobRepository.move_to_dead_letter(db, job, error_message)

        return AIJobRepository.requeue_job(db, job, error_message)
