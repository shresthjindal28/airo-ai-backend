import uuid

from sqlalchemy.orm import Session

from app.agents.soap_agent import SoapAgent
from app.core.logging import get_logger
from app.models.ai_job import AIJob
from app.providers.llm.base import LLMProviderError
from app.repositories.consultation_repository import ConsultationRepository
from app.repositories.consultation_session_repository import (
    ConsultationSessionRepository,
)
from app.repositories.soap_note_repository import SOAPNoteRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.repositories.transcript_segment_repository import (
    TranscriptSegmentRepository,
)
from app.services.audit_service import AuditService

logger = get_logger(__name__)


class SOAPGenerationServiceError(Exception):
    pass


class SOAPGenerationService:

    def __init__(self, agent: SoapAgent | None = None) -> None:
        self._agent = agent or SoapAgent()

    def generate(self, db: Session, job: AIJob) -> None:
        transcript_text = self._load_transcript_text(db, job)
        chief_complaint = self._load_chief_complaint(db, job)

        try:
            content = self._agent.generate(
                transcript=transcript_text,
                chief_complaint=chief_complaint,
            )
        except LLMProviderError as exc:
            raise SOAPGenerationServiceError(str(exc)) from exc

        existing = SOAPNoteRepository.get_by_consultation(db, job.consultation_id)
        regenerate = bool((job.metadata_ or {}).get("regenerate"))

        if existing and not regenerate:
            logger.info(
                "SOAP note already exists consultation_id=%s — skipping",
                job.consultation_id,
            )
            return

        if existing and regenerate:
            soap_note = SOAPNoteRepository.update_soap_note(
                db,
                existing,
                subjective=content.subjective,
                objective=content.objective,
                assessment=content.assessment,
                plan=content.plan,
            )
            action = "SOAP_UPDATED"
        else:
            soap_note = SOAPNoteRepository.create_soap_note(
                db,
                job.consultation_id,
                subjective=content.subjective,
                objective=content.objective,
                assessment=content.assessment,
                plan=content.plan,
            )
            action = "SOAP_CREATED"

        doctor_id = self._resolve_doctor_id(db, job)
        if doctor_id is not None:
            AuditService.log_doctor_action(
                db,
                doctor_id=doctor_id,
                action=action,
                resource_type="soap_note",
                resource_id=soap_note.id,
            )

        logger.info(
            "SOAP note generated consultation_id=%s soap_note_id=%s regenerate=%s",
            job.consultation_id,
            soap_note.id,
            regenerate,
        )

    def _load_transcript_text(self, db: Session, job: AIJob) -> str:
        transcript = TranscriptRepository.get_by_consultation(db, job.consultation_id)
        if transcript and transcript.transcript_text.strip():
            return transcript.transcript_text.strip()

        if job.session_id is None:
            raise SOAPGenerationServiceError(
                "No finalized transcript found for consultation"
            )

        segments = TranscriptSegmentRepository.list_segments_for_session(
            db,
            job.session_id,
        )
        if not segments:
            raise SOAPGenerationServiceError(
                "No transcript segments available for SOAP generation"
            )

        return " ".join(segment.text.strip() for segment in segments if segment.text)

    def _load_chief_complaint(self, db: Session, job: AIJob) -> str | None:
        metadata = job.metadata_ or {}
        chief_complaint = metadata.get("chief_complaint")
        if chief_complaint:
            return str(chief_complaint)

        consultation = ConsultationRepository.get_consultation_by_id(
            db,
            job.consultation_id,
        )
        if consultation is None:
            return None

        return consultation.chief_complaint

    def _resolve_doctor_id(
        self,
        db: Session,
        job: AIJob,
    ) -> uuid.UUID | None:
        if job.session_id is None:
            return None

        session = ConsultationSessionRepository.get_session_by_id(db, job.session_id)
        if session is None:
            return None

        return session.doctor_id
