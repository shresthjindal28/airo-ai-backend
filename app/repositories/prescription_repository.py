import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

import app.models  # noqa: F401
from app.models.prescription import Prescription


class PrescriptionRepository:

    @staticmethod
    def get_current_by_consultation(
        db: Session,
        consultation_id: uuid.UUID,
    ) -> Prescription | None:
        stmt = select(Prescription).where(
            Prescription.consultation_id == consultation_id,
            Prescription.is_current.is_(True),
        )
        return db.scalars(stmt).first()

    @staticmethod
    def get_by_consultation(
        db: Session,
        consultation_id: uuid.UUID,
    ) -> Prescription | None:
        return PrescriptionRepository.get_current_by_consultation(
            db,
            consultation_id,
        )

    @staticmethod
    def _clear_current_flag(db: Session, consultation_id: uuid.UUID) -> None:
        stmt = select(Prescription).where(
            Prescription.consultation_id == consultation_id,
            Prescription.is_current.is_(True),
        )
        for row in db.scalars(stmt).all():
            row.is_current = False
        db.flush()

    @staticmethod
    def create_prescription(
        db: Session,
        *,
        doctor_id: uuid.UUID,
        patient_id: uuid.UUID,
        consultation_id: uuid.UUID,
        soap_note_id: uuid.UUID | None,
        html_content: str,
        plain_text_content: str | None,
        generation_provider: str | None,
        generation_version: str | None,
        version_number: int = 1,
        parent_prescription_id: uuid.UUID | None = None,
    ) -> Prescription:
        PrescriptionRepository._clear_current_flag(db, consultation_id)

        prescription = Prescription(
            doctor_id=doctor_id,
            patient_id=patient_id,
            consultation_id=consultation_id,
            soap_note_id=soap_note_id,
            parent_prescription_id=parent_prescription_id,
            version_number=version_number,
            is_current=True,
            html_content=html_content,
            plain_text_content=plain_text_content,
            generation_provider=generation_provider,
            generation_version=generation_version,
        )
        db.add(prescription)
        db.commit()
        db.refresh(prescription)
        return prescription

    @staticmethod
    def create_version_from_parent(
        db: Session,
        parent: Prescription,
        *,
        html_content: str,
        plain_text_content: str | None,
        generation_provider: str | None,
        generation_version: str | None,
    ) -> Prescription:
        parent.is_current = False
        db.flush()

        prescription = Prescription(
            doctor_id=parent.doctor_id,
            patient_id=parent.patient_id,
            consultation_id=parent.consultation_id,
            soap_note_id=parent.soap_note_id,
            parent_prescription_id=parent.id,
            version_number=parent.version_number + 1,
            is_current=True,
            html_content=html_content,
            plain_text_content=plain_text_content,
            generation_provider=generation_provider,
            generation_version=generation_version,
        )
        db.add(prescription)
        db.commit()
        db.refresh(prescription)
        return prescription

    @staticmethod
    def update_prescription(
        db: Session,
        prescription: Prescription,
        *,
        html_content: str,
        plain_text_content: str | None,
        generation_provider: str | None,
        generation_version: str | None,
    ) -> Prescription:
        prescription.html_content = html_content
        prescription.plain_text_content = plain_text_content
        prescription.generation_provider = generation_provider
        prescription.generation_version = generation_version
        db.commit()
        db.refresh(prescription)
        return prescription
