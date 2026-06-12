import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.soap_note import SOAPNote


class SOAPNoteRepository:

    @staticmethod
    def get_by_consultation(
        db: Session,
        consultation_id: uuid.UUID,
    ) -> SOAPNote | None:
        stmt = select(SOAPNote).where(SOAPNote.consultation_id == consultation_id)
        return db.scalars(stmt).first()

    @staticmethod
    def create_soap_note(
        db: Session,
        consultation_id: uuid.UUID,
        *,
        subjective: str | None = None,
        objective: str | None = None,
        assessment: str | None = None,
        plan: str | None = None,
    ) -> SOAPNote:
        soap_note = SOAPNote(
            consultation_id=consultation_id,
            subjective=subjective,
            objective=objective,
            assessment=assessment,
            plan=plan,
        )
        db.add(soap_note)
        db.commit()
        db.refresh(soap_note)
        return soap_note

    @staticmethod
    def update_soap_note(
        db: Session,
        soap_note: SOAPNote,
        *,
        subjective: str | None = None,
        objective: str | None = None,
        assessment: str | None = None,
        plan: str | None = None,
    ) -> SOAPNote:
        soap_note.subjective = subjective
        soap_note.objective = objective
        soap_note.assessment = assessment
        soap_note.plan = plan
        db.commit()
        db.refresh(soap_note)
        return soap_note
