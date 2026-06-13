import uuid
from datetime import UTC, datetime
from typing import Any

from sqlalchemy import select, text
from sqlalchemy.orm import Session

from app.cache import keys
from app.cache.redis_client import redis_delete_pattern, redis_incr, redis_set_json
from app.core.config import settings
from app.models.patient_memory_profile import PatientMemoryProfile
from app.services.extractive_profile import parse_profile
from app.services.timeline_generation_service import TimelineGenerationService


class PatientBriefingGenerationService:

    def __init__(self) -> None:
        self._timeline_service = TimelineGenerationService()

    def generate(self, db: Session, patient_id: uuid.UUID) -> dict[str, Any]:
        patient_row = db.execute(
            text(
                """
                SELECT full_name, allergies, medical_history
                FROM patients
                WHERE id = :patient_id
                """
            ),
            {"patient_id": str(patient_id)},
        ).mappings().first()

        profile = db.scalars(
            select(PatientMemoryProfile).where(
                PatientMemoryProfile.patient_id == patient_id
            )
        ).first()
        profile_data = parse_profile(profile.summary if profile else "")

        timeline = self._timeline_service.generate(db, patient_id)
        recent_events = (timeline.get("events") or [])[:5]

        allergies: list[str] = []
        allergies_raw = (patient_row or {}).get("allergies")
        if allergies_raw:
            allergies = [
                part.strip()
                for part in str(allergies_raw).replace(";", ",").split(",")
                if part.strip()
            ]

        current_medications = list(profile_data.get("medications") or [])
        diagnoses = list(profile_data.get("diagnoses") or profile_data.get("conditions") or [])
        risk_factors = list(profile_data.get("conditions") or [])
        medical_history = (patient_row or {}).get("medical_history")
        if medical_history:
            risk_factors.append(str(medical_history)[:200])

        patient_name = (patient_row or {}).get("full_name") or "Unknown"
        snapshot_parts = [f"Patient: {patient_name}"]
        if diagnoses:
            snapshot_parts.append(f"Active conditions: {', '.join(diagnoses[:6])}")
        if current_medications:
            snapshot_parts.append(f"Medications: {', '.join(current_medications[:6])}")
        if allergies:
            snapshot_parts.append(f"Allergies: {', '.join(allergies[:6])}")

        briefing = {
            "patient_id": str(patient_id),
            "generated_at": datetime.now(UTC).isoformat(),
            "patient_snapshot": ". ".join(snapshot_parts),
            "current_diagnoses": diagnoses[:20],
            "current_medications": current_medications[:20],
            "risk_factors": risk_factors[:15],
            "allergies": allergies,
            "recent_concerns": [
                e.get("title") or ""
                for e in recent_events
                if e.get("title")
            ][:8],
            "recent_consultations": recent_events,
        }

        redis_set_json(
            keys.patient_briefing(patient_id),
            briefing,
            ttl_seconds=settings.REDIS_PATIENT_CACHE_TTL_SECONDS,
        )
        redis_set_json(
            keys.patient_memory_bundle(patient_id),
            {
                "patient_summary": briefing.get("patient_snapshot"),
                "recent_consultations": briefing.get("recent_consultations"),
                "medication_history": briefing.get("current_medications"),
                "allergy_history": briefing.get("allergies"),
                "risk_factor_summary": ", ".join(briefing.get("risk_factors") or []),
                "generated_at": briefing.get("generated_at"),
            },
            ttl_seconds=settings.REDIS_PATIENT_CACHE_TTL_SECONDS,
        )
        redis_delete_pattern(keys.patient_retrieval_prefix(patient_id))
        redis_delete_pattern(keys.patient_response_prefix(patient_id))
        redis_incr(keys.patient_memory_version(patient_id))
        return briefing
