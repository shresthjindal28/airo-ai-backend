import uuid
from datetime import UTC, datetime

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.agents.prescription_agent import PrescriptionAgent
from app.core.config import settings
from app.core.logging import get_logger
from app.models.ai_job import AIJob
from app.providers.prescription.base import PrescriptionContext, PrescriptionProviderError
from app.providers.prescription.html_utils import (
    build_fallback_prescription_html,
    html_to_plain_text,
)
from app.repositories.consultation_repository import ConsultationRepository
from app.repositories.consultation_session_repository import (
    ConsultationSessionRepository,
)
from app.repositories.prescription_repository import PrescriptionRepository
from app.repositories.soap_note_repository import SOAPNoteRepository
from app.services.audit_service import AuditService

logger = get_logger(__name__)

GENERATION_VERSION = "1.0.0"


class PrescriptionGenerationServiceError(Exception):
    pass


class PrescriptionGenerationService:

    def __init__(self, agent: PrescriptionAgent | None = None) -> None:
        self._agent = agent or PrescriptionAgent()

    def generate(self, db: Session, job: AIJob) -> None:
        soap_note = SOAPNoteRepository.get_by_consultation(db, job.consultation_id)
        if soap_note is None:
            raise PrescriptionGenerationServiceError(
                "SOAP note is required before prescription generation"
            )

        context = self._build_context(db, job, soap_note)
        regenerate = bool((job.metadata_ or {}).get("regenerate"))

        existing = PrescriptionRepository.get_by_consultation(db, job.consultation_id)
        if existing and not regenerate:
            logger.info(
                "Prescription already exists consultation_id=%s — skipping",
                job.consultation_id,
            )
            return

        try:
            html_content, provider_name = self._agent.generate(context)
        except PrescriptionProviderError as exc:
            logger.warning(
                "Prescription LLM failed, using fallback template: %s",
                exc,
            )
            html_content = build_fallback_prescription_html(context)
            provider_name = "fallback:template"

        plain_text = html_to_plain_text(html_content)

        if existing and regenerate:
            prescription = PrescriptionRepository.update_prescription(
                db,
                existing,
                html_content=html_content,
                plain_text_content=plain_text,
                generation_provider=provider_name,
                generation_version=GENERATION_VERSION,
            )
            action = "PRESCRIPTION_UPDATED"
        else:
            prescription = PrescriptionRepository.create_prescription(
                db,
                consultation_id=job.consultation_id,
                html_content=html_content,
                plain_text_content=plain_text,
                generation_provider=provider_name,
                generation_version=GENERATION_VERSION,
            )
            action = "PRESCRIPTION_CREATED"

        doctor_id = self._resolve_doctor_id(db, job)
        if doctor_id is not None:
            AuditService.log_doctor_action(
                db,
                doctor_id=doctor_id,
                action=action,
                resource_type="prescription",
                resource_id=prescription.id,
            )

        logger.info(
            "Prescription generated consultation_id=%s prescription_id=%s regenerate=%s",
            job.consultation_id,
            prescription.id,
            regenerate,
        )

    def _build_context(self, db: Session, job: AIJob, soap_note) -> PrescriptionContext:
        consultation = ConsultationRepository.get_consultation_by_id(
            db,
            job.consultation_id,
        )
        if consultation is None:
            raise PrescriptionGenerationServiceError("Consultation not found")

        patient_row = db.execute(
            text(
                """
                SELECT full_name, date_of_birth, gender::text
                FROM patients
                WHERE id = :patient_id
                """
            ),
            {"patient_id": str(consultation.patient_id)},
        ).mappings().first()

        doctor_row = db.execute(
            text(
                """
                SELECT d.full_name, d.hospital_name, dv.registration_number
                FROM doctors d
                LEFT JOIN doctor_verifications dv ON dv.doctor_id = d.id
                WHERE d.id = :doctor_id
                """
            ),
            {"doctor_id": str(consultation.doctor_id)},
        ).mappings().first()

        metadata = job.metadata_ or {}
        chief_complaint = metadata.get("chief_complaint") or consultation.chief_complaint

        return PrescriptionContext(
            patient_name=(patient_row or {}).get("full_name") or "Patient",
            patient_age=self._format_age((patient_row or {}).get("date_of_birth")),
            patient_gender=self._format_gender((patient_row or {}).get("gender")),
            doctor_name=(doctor_row or {}).get("full_name") or "Attending Physician",
            doctor_registration=(doctor_row or {}).get("registration_number") or "",
            hospital_name=(doctor_row or {}).get("hospital_name") or settings.APP_NAME,
            consultation_date=datetime.now(UTC).strftime("%d %b %Y"),
            chief_complaint=str(chief_complaint or ""),
            subjective=soap_note.subjective or "",
            objective=soap_note.objective or "",
            assessment=soap_note.assessment or "",
            plan=soap_note.plan or "",
        )

    @staticmethod
    def _format_age(date_of_birth) -> str:
        if not date_of_birth:
            return "—"
        today = datetime.now(UTC).date()
        dob = date_of_birth if hasattr(date_of_birth, "year") else datetime.fromisoformat(str(date_of_birth)).date()
        age = today.year - dob.year - (
            (today.month, today.day) < (dob.month, dob.day)
        )
        return str(max(age, 0))

    @staticmethod
    def _format_gender(gender: str | None) -> str:
        if not gender:
            return "—"
        return gender.replace("_", " ").title()

    def _resolve_doctor_id(
        self,
        db: Session,
        job: AIJob,
    ) -> uuid.UUID | None:
        if job.session_id is None:
            consultation = ConsultationRepository.get_consultation_by_id(
                db,
                job.consultation_id,
            )
            return consultation.doctor_id if consultation else None

        session = ConsultationSessionRepository.get_session_by_id(db, job.session_id)
        if session is None:
            return None

        return session.doctor_id
