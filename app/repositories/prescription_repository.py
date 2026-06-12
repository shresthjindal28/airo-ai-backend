import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.prescription import Prescription


class PrescriptionRepository:

    @staticmethod
    def get_by_consultation(
        db: Session,
        consultation_id: uuid.UUID,
    ) -> Prescription | None:
        stmt = select(Prescription).where(
            Prescription.consultation_id == consultation_id
        )
        return db.scalars(stmt).first()

    @staticmethod
    def create_prescription(
        db: Session,
        *,
        consultation_id: uuid.UUID,
        html_content: str,
        plain_text_content: str | None,
        generation_provider: str | None,
        generation_version: str | None,
    ) -> Prescription:
        prescription = Prescription(
            consultation_id=consultation_id,
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
