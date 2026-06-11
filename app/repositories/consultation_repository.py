import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.consultation import Consultation


class ConsultationRepository:

    @staticmethod
    def get_consultation_by_id(
        db: Session,
        consultation_id: uuid.UUID,
    ) -> Consultation | None:
        stmt = select(Consultation).where(Consultation.id == consultation_id)
        return db.scalars(stmt).first()
