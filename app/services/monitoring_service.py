import uuid
from datetime import UTC, datetime
from decimal import Decimal

from sqlalchemy.orm import Session

from app.models.monitoring import JobExecution, STTUsageLog

SARVAM_COST_PER_MINUTE = Decimal("0.006")


class MonitoringService:

    @staticmethod
    def record_job_execution(
        db: Session,
        *,
        job_id: uuid.UUID,
        job_type: str,
        started_at: datetime,
        status: str,
        retry_count: int = 0,
        error: str | None = None,
    ) -> None:
        finished_at = datetime.now(UTC)
        duration_ms = int((finished_at - started_at).total_seconds() * 1000)
        db.add(
            JobExecution(
                job_id=job_id,
                job_type=job_type,
                started_at=started_at,
                finished_at=finished_at,
                duration_ms=duration_ms,
                status=status,
                retry_count=retry_count,
                error=error,
            )
        )
        db.commit()

    @staticmethod
    def log_stt_usage(
        db: Session,
        *,
        provider: str,
        audio_seconds: float,
        characters: int = 0,
        consultation_id: uuid.UUID | None = None,
    ) -> None:
        cost = Decimal(str(audio_seconds)) / Decimal("60") * SARVAM_COST_PER_MINUTE
        db.add(
            STTUsageLog(
                provider=provider,
                audio_seconds=audio_seconds,
                characters=characters,
                consultation_id=consultation_id,
                estimated_cost=cost,
                timestamp=datetime.now(UTC),
            )
        )
        db.commit()
