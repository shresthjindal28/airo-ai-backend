import uuid

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.ai_job import AIJob
from app.publishers.redis_publisher import TranscriptEventPublisher
from app.realtime.merge_buffer import OrderedMergeBuffer
from app.realtime.missing_chunk_tracker import MissingChunkTracker
from app.realtime.session_state import session_state_registry
from app.repositories.consultation_session_repository import (
    ConsultationSessionRepository,
)
from app.repositories.transcript_repository import TranscriptRepository
from app.services.audit_service import AuditService
from app.repositories.transcript_segment_repository import (
    TranscriptSegmentRepository,
)
from app.schemas.transcript_event import TranscriptEvent, TranscriptEventType

logger = get_logger(__name__)


class TranscriptFinalizerError(Exception):
    pass


class TranscriptFinalizer:

    def __init__(self) -> None:
        self._publisher = TranscriptEventPublisher()

    def finalize(self, db: Session, job: AIJob) -> str:
        if job.session_id is None:
            raise TranscriptFinalizerError("transcript_finalize job requires session_id")

        session = ConsultationSessionRepository.get_session_by_id(
            db,
            job.session_id,
        )
        if session is None:
            raise TranscriptFinalizerError(f"Session not found: {job.session_id}")

        segments = TranscriptSegmentRepository.list_segments_for_session(
            db,
            job.session_id,
        )

        merge_buffer = OrderedMergeBuffer()
        missing_tracker = MissingChunkTracker(
            expected_last_chunk=session.last_chunk_number,
        )

        for segment in segments:
            merge_buffer.add(segment.chunk_number, segment.text)
            missing_tracker.register_received(segment.chunk_number)

        missing_tracker.set_expected_last_chunk(session.last_chunk_number)
        merged_text = merge_buffer.merged_text()
        missing_chunks = missing_tracker.missing_chunks()

        if not merged_text.strip() and not segments:
            raise TranscriptFinalizerError("No transcript segments found for session")

        language = "en"
        existing = TranscriptRepository.get_by_consultation(db, job.consultation_id)
        transcript = TranscriptRepository.upsert_transcript(
            db,
            consultation_id=job.consultation_id,
            transcript_text=merged_text,
            language=language,
        )

        AuditService.log_doctor_action(
            db,
            doctor_id=session.doctor_id,
            action="TRANSCRIPT_CREATED" if existing is None else "TRANSCRIPT_UPDATED",
            resource_type="transcript",
            resource_id=transcript.id,
        )
        AuditService.log_doctor_action(
            db,
            doctor_id=session.doctor_id,
            action="TRANSCRIPT_FINALIZED",
            resource_type="transcript",
            resource_id=transcript.id,
        )

        self._publisher.publish(
            TranscriptEvent(
                type=TranscriptEventType.transcript_finalized,
                session_id=job.session_id,
                consultation_id=job.consultation_id,
                merged_text=merged_text,
                missing_chunks=missing_chunks or None,
            )
        )

        session_state_registry.clear(job.session_id)

        logger.info(
            "Transcript finalized session_id=%s segments=%s missing=%s chars=%s",
            job.session_id,
            len(segments),
            len(missing_chunks),
            len(merged_text),
        )

        return merged_text
