import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transcript_segment import TranscriptSegment
from app.schemas.transcript_segment import TranscriptSegmentCreate


class TranscriptSegmentRepository:

    @staticmethod
    def create_segment(
        db: Session,
        data: TranscriptSegmentCreate,
    ) -> TranscriptSegment:
        segment = TranscriptSegment(
            consultation_id=data.consultation_id,
            session_id=data.session_id,
            chunk_id=data.chunk_id,
            chunk_number=data.chunk_number,
            text=data.text,
            confidence_score=data.confidence_score,
            start_time_ms=data.start_time_ms,
            end_time_ms=data.end_time_ms,
            provider=data.provider,
            processing_latency_ms=data.processing_latency_ms,
        )
        db.add(segment)
        db.commit()
        db.refresh(segment)
        return segment

    @staticmethod
    def get_by_chunk_id(
        db: Session,
        chunk_id: uuid.UUID,
    ) -> TranscriptSegment | None:
        stmt = select(TranscriptSegment).where(
            TranscriptSegment.chunk_id == chunk_id
        )
        return db.scalars(stmt).first()

    @staticmethod
    def list_segments_for_session(
        db: Session,
        session_id: uuid.UUID,
    ) -> list[TranscriptSegment]:
        stmt = (
            select(TranscriptSegment)
            .where(TranscriptSegment.session_id == session_id)
            .order_by(TranscriptSegment.chunk_number.asc())
        )
        return list(db.scalars(stmt).all())
