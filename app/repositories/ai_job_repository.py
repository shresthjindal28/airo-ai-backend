import random
import uuid
from datetime import UTC, datetime, timedelta

from sqlalchemy import case, or_, select
from sqlalchemy.orm import Session

from typing import Any

from app.models.ai_job import AIJob
from app.models.dead_letter_job import DeadLetterJob
from app.models.enums import AIJobStatus, AIJobType, JobPriority

_BASE_BACKOFF_SECONDS = 5
_MAX_BACKOFF_SECONDS = 300


def _retry_delay_seconds(attempt_count: int) -> float:
    exp = min(_MAX_BACKOFF_SECONDS, _BASE_BACKOFF_SECONDS * (2 ** max(0, attempt_count - 1)))
    jitter = random.uniform(0, exp * 0.25)
    return min(_MAX_BACKOFF_SECONDS, exp + jitter)


class AIJobRepository:

    @staticmethod
    def create_job(
        db: Session,
        consultation_id: uuid.UUID,
        job_type: AIJobType,
        session_id: uuid.UUID | None = None,
        priority: JobPriority = JobPriority.normal,
        metadata: dict[str, Any] | None = None,
        status: AIJobStatus = AIJobStatus.pending,
    ) -> AIJob:
        job = AIJob(
            consultation_id=consultation_id,
            session_id=session_id,
            job_type=job_type,
            priority=priority,
            metadata_=metadata,
            status=status,
        )
        db.add(job)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def get_job_by_id(db: Session, job_id: uuid.UUID) -> AIJob | None:
        stmt = select(AIJob).where(AIJob.id == job_id)
        return db.scalars(stmt).first()

    @staticmethod
    def get_queued_jobs(db: Session, limit: int = 100) -> list[AIJob]:
        priority_order = case(
            (AIJob.priority == JobPriority.critical, 0),
            (AIJob.priority == JobPriority.high, 1),
            (AIJob.priority == JobPriority.normal, 2),
            (AIJob.priority == JobPriority.low, 3),
            else_=4,
        )
        now = datetime.now(UTC)

        stmt = (
            select(AIJob)
            .where(
                AIJob.status.in_([AIJobStatus.pending, AIJobStatus.queued]),
                or_(AIJob.retry_after.is_(None), AIJob.retry_after <= now),
            )
            .order_by(priority_order, AIJob.created_at.asc())
            .limit(limit)
        )
        return list(db.scalars(stmt).all())

    @staticmethod
    def claim_job(db: Session) -> AIJob | None:
        priority_order = case(
            (AIJob.priority == JobPriority.critical, 0),
            (AIJob.priority == JobPriority.high, 1),
            (AIJob.priority == JobPriority.normal, 2),
            (AIJob.priority == JobPriority.low, 3),
            else_=4,
        )
        now = datetime.now(UTC)

        stmt = (
            select(AIJob)
            .where(
                AIJob.status.in_([AIJobStatus.pending, AIJobStatus.queued]),
                or_(AIJob.retry_after.is_(None), AIJob.retry_after <= now),
            )
            .order_by(priority_order, AIJob.created_at.asc())
            .limit(1)
            .with_for_update(skip_locked=True)
        )
        job = db.scalars(stmt).first()

        if job is None:
            db.rollback()
            return None

        job.status = AIJobStatus.processing
        job.started_at = datetime.now(UTC)
        job.error_message = None
        job.attempt_count += 1
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_processing(db: Session, job: AIJob) -> AIJob:
        job.status = AIJobStatus.processing
        job.started_at = datetime.now(UTC)
        job.error_message = None
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_completed(db: Session, job: AIJob) -> AIJob:
        job.status = AIJobStatus.completed
        job.completed_at = datetime.now(UTC)
        job.error_message = None
        job.retry_after = None
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def mark_failed(
        db: Session,
        job: AIJob,
        error_message: str,
    ) -> AIJob:
        job.status = AIJobStatus.failed
        job.error_message = error_message
        job.completed_at = datetime.now(UTC)
        job.retry_after = None
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def increment_attempts(db: Session, job: AIJob) -> AIJob:
        job.attempt_count += 1
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def requeue_job(db: Session, job: AIJob, error_message: str) -> AIJob:
        delay = _retry_delay_seconds(job.attempt_count)
        job.status = AIJobStatus.queued
        job.started_at = None
        job.error_message = error_message
        job.retry_after = datetime.now(UTC) + timedelta(seconds=delay)
        db.commit()
        db.refresh(job)
        return job

    @staticmethod
    def move_to_dead_letter(db: Session, job: AIJob, error_message: str) -> DeadLetterJob:
        now = datetime.now(UTC)
        dlq = DeadLetterJob(
            id=uuid.uuid4(),
            original_job_id=job.id,
            consultation_id=job.consultation_id,
            session_id=job.session_id,
            job_type=job.job_type,
            priority=job.priority,
            attempt_count=job.attempt_count,
            error_message=error_message,
            metadata_=job.metadata_,
            failed_at=now,
            created_at=job.created_at,
        )
        db.add(dlq)
        job.status = AIJobStatus.failed
        job.error_message = error_message
        job.completed_at = now
        job.retry_after = None
        db.commit()
        db.refresh(dlq)
        return dlq
