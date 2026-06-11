import uuid

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.models.transcript import Transcript


class TranscriptRepository:

    @staticmethod
    def get_by_consultation(
        db: Session,
        consultation_id: uuid.UUID,
    ) -> Transcript | None:
        stmt = select(Transcript).where(
            Transcript.consultation_id == consultation_id
        )
        return db.scalars(stmt).first()

    @staticmethod
    def upsert_transcript(
        db: Session,
        consultation_id: uuid.UUID,
        transcript_text: str,
        language: str = "en",
    ) -> Transcript:
        existing = TranscriptRepository.get_by_consultation(db, consultation_id)

        if existing:
            existing.transcript_text = transcript_text
            if language:
                existing.language = language
            db.commit()
            db.refresh(existing)
            return existing

        transcript = Transcript(
            consultation_id=consultation_id,
            transcript_text=transcript_text,
            language=language,
        )
        db.add(transcript)
        db.commit()
        db.refresh(transcript)
        return transcript
