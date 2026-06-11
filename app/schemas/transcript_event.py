import uuid
from enum import Enum

from pydantic import BaseModel

from app.schemas.transcript_segment import TranscriptSegmentResponse


class TranscriptEventType(str, Enum):
    segment_created = "segment_created"
    segment_updated = "segment_updated"
    transcript_finalized = "transcript_finalized"


class TranscriptEvent(BaseModel):
    type: TranscriptEventType
    session_id: uuid.UUID
    consultation_id: uuid.UUID
    segment: TranscriptSegmentResponse | None = None
    merged_text: str | None = None
    missing_chunks: list[int] | None = None
