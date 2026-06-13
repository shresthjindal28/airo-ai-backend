import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AIJobType, JobPriority
from app.models.mixins import UUIDPrimaryKeyMixin


class DeadLetterJob(UUIDPrimaryKeyMixin, Base):
    __tablename__ = "dead_letter_jobs"
    __table_args__ = (
        Index("ix_dead_letter_jobs_consultation_id", "consultation_id"),
        Index("ix_dead_letter_jobs_failed_at", "failed_at"),
    )

    original_job_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
    )
    consultation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
    )
    job_type: Mapped[AIJobType] = mapped_column(
        Enum(AIJobType, name="ai_job_type", create_type=False),
        nullable=False,
    )
    priority: Mapped[JobPriority] = mapped_column(
        Enum(JobPriority, name="job_priority", create_type=False),
        nullable=False,
    )
    attempt_count: Mapped[int] = mapped_column(Integer, nullable=False)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
    failed_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
    created_at: Mapped[datetime] = mapped_column(
        DateTime(timezone=True),
        nullable=False,
        default=lambda: datetime.now(UTC),
    )
