import time
import uuid

from sqlalchemy.orm import Session

from app.core.logging import get_logger
from app.models.ai_job import AIJob
from app.models.enums import ChunkStatus
from app.providers.registry import get_speech_to_text_provider
from app.publishers.redis_publisher import TranscriptEventPublisher
from app.realtime.session_state import session_state_registry
from app.repositories.audio_chunk_repository import AudioChunkRepository
from app.repositories.transcript_segment_repository import TranscriptSegmentRepository
from app.schemas.transcript_event import TranscriptEvent, TranscriptEventType
from app.schemas.transcript_segment import (
    TranscriptSegmentCreate,
    TranscriptSegmentResponse,
)
from app.services.storage_service import StorageService

logger = get_logger(__name__)


class TranscriptionServiceError(Exception):
    pass


class TranscriptionService:

    def __init__(self) -> None:
        self._publisher = TranscriptEventPublisher()

    def process_job(self, db: Session, job: AIJob) -> None:
        metadata = job.metadata_ or {}
        chunk_id_raw = metadata.get("chunk_id")

        if not chunk_id_raw:
            raise TranscriptionServiceError("Job metadata missing chunk_id")

        chunk_id = uuid.UUID(str(chunk_id_raw))
        existing = TranscriptSegmentRepository.get_by_chunk_id(db, chunk_id)

        if existing:
            logger.info(
                "Transcript segment already exists chunk_id=%s job_id=%s",
                chunk_id,
                job.id,
            )
            self._publish_existing_segment(existing)
            return

        chunk = AudioChunkRepository.get_chunk_by_id(db, chunk_id)
        if chunk is None:
            raise TranscriptionServiceError(f"Audio chunk not found: {chunk_id}")

        AudioChunkRepository.update_status(db, chunk, ChunkStatus.processing)

        started = time.perf_counter()
        audio_bytes = StorageService.download_object(chunk.object_key)
        provider = get_speech_to_text_provider()
        result = provider.transcribe_chunk(
            audio_bytes,
            mime_type=chunk.mime_type,
        )
        processing_latency_ms = int((time.perf_counter() - started) * 1000)

        start_time_ms = max(0, (chunk.chunk_number - 1) * chunk.duration_ms)
        end_time_ms = start_time_ms + chunk.duration_ms

        segment = TranscriptSegmentRepository.create_segment(
            db,
            TranscriptSegmentCreate(
                consultation_id=chunk.consultation_id,
                session_id=chunk.session_id,
                chunk_id=chunk.id,
                chunk_number=chunk.chunk_number,
                text=result.text,
                confidence_score=result.confidence_score,
                start_time_ms=start_time_ms,
                end_time_ms=end_time_ms,
                provider=provider.provider_name,
                processing_latency_ms=processing_latency_ms,
            ),
        )

        AudioChunkRepository.update_status(db, chunk, ChunkStatus.processed)

        segment_response = TranscriptSegmentResponse.model_validate(segment)
        self._update_session_state(chunk.session_id, segment_response)
        self._publisher.publish(
            TranscriptEvent(
                type=TranscriptEventType.segment_created,
                session_id=segment.session_id,
                consultation_id=segment.consultation_id,
                segment=segment_response,
            )
        )

        logger.info(
            "Transcription complete job_id=%s chunk_number=%s latency_ms=%s",
            job.id,
            chunk.chunk_number,
            processing_latency_ms,
        )

    def _update_session_state(
        self,
        session_id: uuid.UUID,
        segment: TranscriptSegmentResponse,
    ) -> None:
        state = session_state_registry.get(session_id)
        state.segment_index.put(segment.chunk_number, segment)
        state.merge_buffer.add(segment.chunk_number, segment.text)
        state.missing_tracker.register_received(segment.chunk_number)
        state.ring_buffer.append(segment)

    def _publish_existing_segment(self, segment) -> None:
        segment_response = TranscriptSegmentResponse.model_validate(segment)
        self._update_session_state(segment.session_id, segment_response)
        self._publisher.publish(
            TranscriptEvent(
                type=TranscriptEventType.segment_updated,
                session_id=segment.session_id,
                consultation_id=segment.consultation_id,
                segment=segment_response,
            )
        )
