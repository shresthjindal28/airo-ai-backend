import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.consultation_session import ConsultationSession


class ConsultationSessionRepository:

    @staticmethod
    def get_session_by_id(
        db: Session,
        session_id: uuid.UUID,
    ) -> ConsultationSession | None:
        stmt = select(ConsultationSession).where(
            ConsultationSession.id == session_id
        )
        return db.scalars(stmt).first()
