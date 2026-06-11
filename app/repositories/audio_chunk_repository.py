import uuid
from datetime import UTC, datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.audio_chunk import AudioChunk
from app.models.enums import ChunkStatus


class AudioChunkRepository:

    @staticmethod
    def get_chunk_by_id(db: Session, chunk_id: uuid.UUID) -> AudioChunk | None:
        stmt = select(AudioChunk).where(AudioChunk.id == chunk_id)
        return db.scalars(stmt).first()

    @staticmethod
    def update_status(
        db: Session,
        chunk: AudioChunk,
        status: ChunkStatus,
    ) -> AudioChunk:
        chunk.status = status
        if status == ChunkStatus.processed:
            chunk.processed_at = datetime.now(UTC)
        db.commit()
        db.refresh(chunk)
        return chunk
