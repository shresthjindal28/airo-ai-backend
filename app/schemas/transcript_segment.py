import uuid
from datetime import datetime

from pydantic import BaseModel, ConfigDict


class TranscriptSegmentCreate(BaseModel):
    consultation_id: uuid.UUID
    session_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_number: int
    text: str
    confidence_score: float | None = None
    start_time_ms: int
    end_time_ms: int
    provider: str
    processing_latency_ms: int | None = None


class TranscriptSegmentResponse(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: uuid.UUID
    consultation_id: uuid.UUID
    session_id: uuid.UUID
    chunk_id: uuid.UUID
    chunk_number: int
    text: str
    confidence_score: float | None = None
    start_time_ms: int
    end_time_ms: int
    provider: str
    processing_latency_ms: int | None = None
    created_at: datetime
