import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.cache import keys
from app.cache.invalidation import invalidate_patient_caches
from app.cache.redis_client import redis_set_json
from app.core.config import settings
from app.models.consultation import Consultation
from app.models.enums import ConsultationStatus, MemorySourceType
from app.models.memory_document import MemoryDocument
from app.models.patient_memory_profile import PatientMemoryProfile
from app.models.prescription import Prescription
from app.services.extractive_profile import parse_profile


class TimelineGenerationService:

    def generate(self, db: Session, patient_id: uuid.UUID) -> dict[str, Any]:
        stmt = (
            select(Consultation)
            .where(
                Consultation.patient_id == patient_id,
                Consultation.is_active.is_(True),
            )
            .order_by(Consultation.created_at.asc())
        )
        consultations = list(db.scalars(stmt).all())

        doc_stmt = (
            select(MemoryDocument)
            .where(MemoryDocument.patient_id == patient_id)
            .order_by(MemoryDocument.created_at.asc())
            .limit(200)
        )
        documents = list(db.scalars(doc_stmt).all())

        rx_stmt = (
            select(Prescription)
            .where(Prescription.patient_id == patient_id)
            .order_by(Prescription.created_at.asc())
        )
        prescriptions = list(db.scalars(rx_stmt).all())

        profile = db.scalars(
            select(PatientMemoryProfile).where(
                PatientMemoryProfile.patient_id == patient_id
            )
        ).first()
        profile_data = parse_profile(profile.summary if profile else "")

        events: list[dict[str, Any]] = []
        medication_progression: list[dict[str, Any]] = []
        disease_progression: list[dict[str, Any]] = []
        milestones: list[dict[str, Any]] = []

        for consultation in consultations:
            events.append({
                "date": consultation.created_at.isoformat(),
                "type": "consultation",
                "consultation_id": str(consultation.id),
                "title": consultation.chief_complaint or "Consultation",
                "status": consultation.status.value,
            })
            if consultation.status == ConsultationStatus.completed:
                milestones.append({
                    "date": consultation.created_at.isoformat(),
                    "type": "consultation_completed",
                    "title": consultation.chief_complaint or "Visit completed",
                })

        for doc in documents:
            if doc.source_type in (
                MemorySourceType.soap_note,
                MemorySourceType.prescription,
            ):
                events.append({
                    "date": doc.created_at.isoformat(),
                    "type": doc.source_type.value,
                    "title": doc.title,
                    "summary": (doc.content or "")[:240],
                })

        for rx in prescriptions:
            if rx.is_approved:
                medication_progression.append({
                    "date": (rx.approved_at or rx.created_at).isoformat(),
                    "version": rx.version_number,
                    "summary": (rx.plain_text_content or "")[:200],
                })

        for condition in profile_data.get("conditions", []):
            disease_progression.append({
                "date": None,
                "finding": condition,
                "source": "profile",
            })

        events.sort(key=lambda e: e.get("date") or "", reverse=True)

        timeline = {
            "patient_id": str(patient_id),
            "generated_at": datetime.now(UTC).isoformat(),
            "events": events[:80],
            "medication_progression": medication_progression[:40],
            "disease_progression": disease_progression[:40],
            "visit_summaries": [e for e in events if e["type"] == "consultation"][:20],
            "treatment_changes": medication_progression[:20],
            "milestones": milestones[:30],
            "consultation_count": len(consultations),
        }

        redis_set_json(
            keys.patient_timeline(patient_id),
            timeline,
            ttl_seconds=settings.REDIS_TIMELINE_CACHE_TTL_SECONDS,
        )
        invalidate_patient_caches(patient_id)
        return timeline
