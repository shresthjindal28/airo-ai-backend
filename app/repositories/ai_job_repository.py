import uuid
from datetime import UTC, datetime

from sqlalchemy import case, select
from sqlalchemy.orm import Session

from app.models.ai_job import AIJob
from app.models.enums import AIJobStatus, JobPriority


class AIJobRepository:

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

        stmt = (
            select(AIJob)
            .where(AIJob.status.in_([AIJobStatus.pending, AIJobStatus.queued]))
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

        stmt = (
            select(AIJob)
            .where(AIJob.status.in_([AIJobStatus.pending, AIJobStatus.queued]))
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
        job.status = AIJobStatus.queued
        job.started_at = None
        job.error_message = error_message
        db.commit()
        db.refresh(job)
        return job
