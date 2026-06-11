import uuid
from datetime import datetime
from typing import Any

from sqlalchemy import DateTime, Enum, ForeignKey, Index, Integer, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column

from app.models.base import Base
from app.models.enums import AIJobStatus, AIJobType, JobPriority
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin


class AIJob(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "ai_jobs"
    __table_args__ = (
        Index("ix_ai_jobs_priority_status", "priority", "status"),
    )

    consultation_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultations.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    session_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        ForeignKey("consultation_sessions.id", ondelete="SET NULL"),
        nullable=True,
        index=True,
    )
    job_type: Mapped[AIJobType] = mapped_column(
        Enum(AIJobType, name="ai_job_type", create_type=False),
        nullable=False,
        index=True,
    )
    status: Mapped[AIJobStatus] = mapped_column(
        Enum(AIJobStatus, name="ai_job_status", create_type=False),
        nullable=False,
        default=AIJobStatus.pending,
        server_default="pending",
        index=True,
    )
    priority: Mapped[JobPriority] = mapped_column(
        Enum(JobPriority, name="job_priority", create_type=False),
        nullable=False,
        default=JobPriority.normal,
        server_default="normal",
    )
    attempt_count: Mapped[int] = mapped_column(
        Integer,
        nullable=False,
        default=0,
        server_default="0",
    )
    started_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    completed_at: Mapped[datetime | None] = mapped_column(
        DateTime(timezone=True),
        nullable=True,
    )
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )
