import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.exc import IntegrityError
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.ai_job import AIJob
from app.models.enums import MemorySourceType
from app.models.memory_chunk import MemoryChunk
from app.models.memory_document import MemoryDocument
from app.models.patient_memory_profile import PatientMemoryProfile
from app.models.prescription import Prescription
from app.models.soap_note import SOAPNote
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.registry import get_embedding_provider
from app.repositories.consultation_repository import ConsultationRepository
from app.repositories.transcript_repository import TranscriptRepository
from app.services.audit_service import AuditService
from app.services.memory_chunker import chunk_text, estimate_token_count
from app.services.extractive_profile import merge_profile

logger = get_logger(__name__)


class MemoryIngestionError(Exception):
    pass


class MemoryIngestionService:

    def ingest(
        self,
        db: Session,
        job: AIJob,
        *,
        provider: EmbeddingProvider | None = None,
        defer_commit: bool = False,
    ) -> uuid.UUID:
        metadata = job.metadata_ or {}
        source_type_raw = metadata.get("source_type")
        source_id_raw = metadata.get("source_id")
        patient_id_raw = metadata.get("patient_id")

        if not source_type_raw or not source_id_raw:
            raise MemoryIngestionError("memory_ingestion job requires source metadata")

        source_type = MemorySourceType(source_type_raw)
        source_id = uuid.UUID(str(source_id_raw))

        consultation = ConsultationRepository.get_consultation_by_id(
            db,
            job.consultation_id,
        )
        if consultation is None:
            raise MemoryIngestionError(f"Consultation not found: {job.consultation_id}")

        patient_id = (
            uuid.UUID(str(patient_id_raw))
            if patient_id_raw
            else consultation.patient_id
        )

        existing_stmt = select(MemoryDocument).where(
            MemoryDocument.source_type == source_type,
            MemoryDocument.source_id == source_id,
        )
        existing = db.scalars(existing_stmt).first()
        if existing is not None:
            logger.info(
                "Memory document already exists source_type=%s source_id=%s",
                source_type,
                source_id,
            )
            return existing.id

        title, content, extra_metadata = self._load_source_content(
            db,
            source_type=source_type,
            source_id=source_id,
            consultation_id=job.consultation_id,
        )

        document = MemoryDocument(
            patient_id=patient_id,
            consultation_id=job.consultation_id,
            source_type=source_type,
            source_id=source_id,
            title=title,
            content=content,
            metadata_=extra_metadata,
        )
        db.add(document)
        db.flush()

        chunks = chunk_text(content)
        embed_provider = provider or get_embedding_provider()
        embeddings = embed_provider.embed_batch(chunks) if chunks else []

        for index, chunk_text_value in enumerate(chunks):
            embedding = embeddings[index] if index < len(embeddings) else None
            chunk = MemoryChunk(
                document_id=document.id,
                chunk_index=index,
                chunk_text=chunk_text_value,
                token_count=estimate_token_count(chunk_text_value),
                embedding=embedding,
                embedding_id=f"{document.id}:{index}",
            )
            db.add(chunk)

        profile = self._upsert_profile(
            db,
            patient_id,
            title,
            content,
            source_type=source_type,
            consultation=consultation,
        )
        if defer_commit:
            db.flush()
        else:
            db.commit()
            db.refresh(document)

        if defer_commit:
            return document.id

        AuditService.log_doctor_action(
            db,
            doctor_id=consultation.doctor_id,
            action="MEMORY_DOCUMENT_CREATED",
            resource_type="memory_document",
            resource_id=document.id,
        )
        AuditService.log_doctor_action(
            db,
            doctor_id=consultation.doctor_id,
            action="MEMORY_PROFILE_UPDATED",
            resource_type="patient_memory_profile",
            resource_id=profile.id,
        )

        try:
            from app.cache.invalidation import invalidate_patient_caches

            invalidate_patient_caches(patient_id)
        except Exception:
            logger.warning(
                "Failed to invalidate patient caches patient_id=%s",
                patient_id,
                exc_info=True,
            )

        logger.info(
            "Memory ingested document_id=%s patient_id=%s chunks=%s",
            document.id,
            patient_id,
            len(chunks),
        )
        return document.id

    def ingest_many(
        self,
        db: Session,
        jobs: list[AIJob],
        *,
        provider: EmbeddingProvider | None = None,
    ) -> list[uuid.UUID]:
        embed_provider = provider or get_embedding_provider()
        document_ids: list[uuid.UUID] = []

        for job in jobs:
            document_ids.append(
                self.ingest(
                    db,
                    job,
                    provider=embed_provider,
                    defer_commit=True,
                )
            )

        db.commit()
        return document_ids

    @staticmethod
    def _load_source_content(
        db: Session,
        *,
        source_type: MemorySourceType,
        source_id: uuid.UUID,
        consultation_id: uuid.UUID,
    ) -> tuple[str, str, dict[str, Any] | None]:
        if source_type == MemorySourceType.transcript:
            if not settings.MEMORY_INGEST_TRANSCRIPT_SOURCES:
                raise MemoryIngestionError(
                    "Transcript memory ingestion is disabled; ingest SOAP notes and approved prescriptions only"
                )
            transcript = TranscriptRepository.get_by_consultation(db, consultation_id)
            if transcript is None:
                raise MemoryIngestionError("Transcript not found for consultation")
            return (
                "Consultation Transcript",
                transcript.transcript_text,
                {"language": transcript.language},
            )

        if source_type == MemorySourceType.soap_note:
            soap_note = db.get(SOAPNote, source_id)
            if soap_note is None:
                raise MemoryIngestionError(f"SOAP note not found: {source_id}")

            sections = [
                ("Subjective", soap_note.subjective),
                ("Objective", soap_note.objective),
                ("Assessment", soap_note.assessment),
                ("Plan", soap_note.plan),
            ]
            content_parts = [
                f"{label}:\n{value.strip()}"
                for label, value in sections
                if value and value.strip()
            ]
            if not content_parts:
                raise MemoryIngestionError("SOAP note has no content to ingest")

            return (
                "SOAP Note",
                "\n\n".join(content_parts),
                {
                    "approved": soap_note.approved_by_doctor,
                    "document_type": "soap_note",
                    "soap_note_id": str(soap_note.id),
                    "consultation_id": str(soap_note.consultation_id),
                },
            )

        if source_type == MemorySourceType.prescription:
            prescription = db.get(Prescription, source_id)
            if prescription is None:
                raise MemoryIngestionError(f"Prescription not found: {source_id}")

            if not prescription.is_approved:
                raise MemoryIngestionError(
                    "Only approved prescriptions can be ingested into patient memory"
                )

            content = (prescription.plain_text_content or "").strip()
            if not content:
                from app.providers.prescription.html_utils import html_to_plain_text

                content = html_to_plain_text(prescription.html_content).strip()
            if not content:
                raise MemoryIngestionError("Prescription has no content to ingest")

            return (
                f"Prescription v{prescription.version_number}",
                content,
                {
                    "patient_id": str(prescription.patient_id),
                    "doctor_id": str(prescription.doctor_id),
                    "consultation_id": str(prescription.consultation_id),
                    "prescription_id": str(prescription.id),
                    "soap_note_id": (
                        str(prescription.soap_note_id)
                        if prescription.soap_note_id
                        else None
                    ),
                    "document_type": "prescription",
                    "approved": prescription.is_approved,
                    "version_number": prescription.version_number,
                },
            )

        raise MemoryIngestionError(f"Unsupported memory source type: {source_type}")

    @staticmethod
    def _upsert_profile(
        db: Session,
        patient_id: uuid.UUID,
        title: str,
        content: str,
        *,
        source_type: MemorySourceType,
        consultation,
    ) -> PatientMemoryProfile:
        stmt = select(PatientMemoryProfile).where(
            PatientMemoryProfile.patient_id == patient_id
        )
        profile = db.scalars(stmt).first()
        now = datetime.now(UTC)
        consultation_date = getattr(consultation, "created_at", None) or now

        summary = merge_profile(
            profile.summary if profile is not None else "",
            document_title=title,
            content=content,
            source_type=source_type.value,
            consultation_date=consultation_date,
        )

        if profile is None:
            profile = PatientMemoryProfile(
                patient_id=patient_id,
                summary=summary,
                last_updated_at=now,
            )
            db.add(profile)
            try:
                with db.begin_nested():
                    db.flush()
            except IntegrityError:
                profile = db.scalars(stmt).first()
                if profile is None:
                    raise
                profile.summary = summary
                profile.last_updated_at = now
                db.flush()
        else:
            profile.summary = summary
            profile.last_updated_at = now
            db.flush()

        return profile
