"""Re-hydrate archived transcript segments from R2 back into PostgreSQL."""

from __future__ import annotations

import gzip
import json
import uuid

from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.transcript_segment import TranscriptSegment
from app.services.transcript_archive_worker import ARCHIVE_KEY_PREFIX, _get_r2_client

logger = get_logger(__name__)


class TranscriptRestoreWorker:
    """Restore cold transcript segments into hot PostgreSQL storage."""

    def restore_session(self, db: Session, session_id: uuid.UUID) -> int:
        archive = db.execute(
            text(
                """
                SELECT archive_key, checksum_sha256, consultation_id, segment_count
                FROM transcript_segment_archives
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        ).mappings().first()
        if archive is None:
            return 0

        existing = db.execute(
            text(
                """
                SELECT COUNT(*) FROM transcript_segments
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        ).scalar_one()
        if existing:
            return 0

        response = _get_r2_client().get_object(
            Bucket=settings.R2_BUCKET_NAME,
            Key=archive["archive_key"],
        )
        body = response["Body"].read()
        if response.get("ContentEncoding") == "gzip":
            body = gzip.decompress(body)

        import hashlib

        if hashlib.sha256(body).hexdigest() != archive["checksum_sha256"]:
            raise ValueError(f"Checksum mismatch for session_id={session_id}")

        payload = json.loads(body.decode("utf-8"))
        consultation_id = archive["consultation_id"]

        for item in payload:
            segment = TranscriptSegment(
                id=uuid.UUID(item["id"]) if item.get("id") else uuid.uuid4(),
                consultation_id=consultation_id,
                session_id=session_id,
                chunk_id=uuid.UUID(item["chunk_id"]),
                chunk_number=int(item["chunk_number"]),
                text=item["text"],
                confidence_score=item.get("confidence_score"),
                start_time_ms=int(item["start_time_ms"]),
                end_time_ms=int(item["end_time_ms"]),
                provider=item["provider"],
                processing_latency_ms=item.get("processing_latency_ms"),
            )
            db.add(segment)

        db.execute(
            text(
                """
                UPDATE transcript_segment_archives
                SET restored_at = now()
                WHERE session_id = :session_id
                """
            ),
            {"session_id": session_id},
        )
        db.commit()
        logger.info(
            "Restored transcript segments session_id=%s count=%s",
            session_id,
            len(payload),
        )
        return len(payload)
