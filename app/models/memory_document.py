import uuid
from typing import TYPE_CHECKING, Any

from sqlalchemy import Enum, String, Text
from sqlalchemy.dialects.postgresql import JSONB, UUID
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.models.base import Base
from app.models.enums import MemorySourceType
from app.models.mixins import TimestampMixin, UUIDPrimaryKeyMixin

if TYPE_CHECKING:
    from app.models.memory_chunk import MemoryChunk


class MemoryDocument(UUIDPrimaryKeyMixin, TimestampMixin, Base):
    __tablename__ = "memory_documents"

    patient_id: Mapped[uuid.UUID] = mapped_column(
        UUID(as_uuid=True),
        nullable=False,
        index=True,
    )
    consultation_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    source_type: Mapped[MemorySourceType] = mapped_column(
        Enum(MemorySourceType, name="memory_source_type", create_type=False),
        nullable=False,
        index=True,
    )
    source_id: Mapped[uuid.UUID | None] = mapped_column(
        UUID(as_uuid=True),
        nullable=True,
        index=True,
    )
    title: Mapped[str] = mapped_column(String(500), nullable=False)
    content: Mapped[str] = mapped_column(Text, nullable=False)
    metadata_: Mapped[dict[str, Any] | None] = mapped_column(
        "metadata",
        JSONB,
        nullable=True,
    )

    chunks: Mapped[list["MemoryChunk"]] = relationship(
        back_populates="document",
        cascade="all, delete-orphan",
    )
