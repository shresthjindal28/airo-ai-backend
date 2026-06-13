import gzip
import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import boto3
from botocore.config import Config
from sqlalchemy import delete, select, text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger
from app.models.transcript_segment import TranscriptSegment
from app.repositories.transcript_segment_repository import (
    TranscriptSegmentRepository,
)

logger = get_logger(__name__)

ARCHIVE_KEY_PREFIX = "transcript-archives"


@lru_cache
def _get_r2_client():
    return boto3.client(
        "s3",
        endpoint_url=settings.R2_ENDPOINT_URL,
        aws_access_key_id=settings.R2_ACCESS_KEY_ID,
        aws_secret_access_key=settings.R2_SECRET_ACCESS_KEY,
        region_name="auto",
        config=Config(signature_version="s3v4"),
    )


def _serialize_segments(segments) -> bytes:
    import json

    payload = [
        {
            "id": str(segment.id),
            "chunk_id": str(segment.chunk_id),
            "chunk_number": segment.chunk_number,
            "text": segment.text,
            "confidence_score": segment.confidence_score,
            "start_time_ms": segment.start_time_ms,
            "end_time_ms": segment.end_time_ms,
            "provider": segment.provider,
            "processing_latency_ms": segment.processing_latency_ms,
            "created_at": segment.created_at.isoformat() if segment.created_at else None,
        }
        for segment in segments
    ]
    return json.dumps(payload, separators=(",", ":"), ensure_ascii=False).encode("utf-8")


def _checksum(data: bytes) -> str:
    import hashlib

    return hashlib.sha256(data).hexdigest()


class TranscriptArchiveWorker:
    """Move transcript segments older than hot window to compressed R2 archives."""

    def run(self, db: Session) -> dict:
        cutoff = datetime.now(UTC) - timedelta(days=settings.TRANSCRIPT_ARCHIVE_HOT_DAYS)
        session_rows = db.execute(
            text(
                """
                SELECT DISTINCT session_id, consultation_id
                FROM transcript_segments
                WHERE created_at < :cutoff
                ORDER BY session_id
                LIMIT :batch_size
                """
            ),
            {
                "cutoff": cutoff,
                "batch_size": settings.TRANSCRIPT_ARCHIVE_BATCH_SIZE,
            },
        ).mappings().all()

        archived_sessions = 0
        deleted_segments = 0

        for row in session_rows:
            session_id = row["session_id"]
            consultation_id = row["consultation_id"]

            existing = db.execute(
                text(
                    """
                    SELECT 1 FROM transcript_segment_archives
                    WHERE session_id = :session_id
                    """
                ),
                {"session_id": session_id},
            ).first()
            if existing:
                continue

            segments = TranscriptSegmentRepository.list_segments_for_session(
                db,
                session_id,
            )
            if not segments:
                continue

            raw = _serialize_segments(segments)
            compressed = gzip.compress(raw, compresslevel=6)
            archive_key = (
                f"{ARCHIVE_KEY_PREFIX}/{consultation_id}/{session_id}.json.gz"
            )
            digest = _checksum(raw)

            _get_r2_client().put_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=archive_key,
                Body=compressed,
                ContentType="application/json",
                ContentEncoding="gzip",
                Metadata={"checksum-sha256": digest},
            )

            db.execute(
                text(
                    """
                    INSERT INTO transcript_segment_archives (
                        id, session_id, consultation_id, segment_count,
                        archive_key, compressed_bytes, checksum_sha256
                    ) VALUES (
                        gen_random_uuid(), :session_id, :consultation_id, :segment_count,
                        :archive_key, :compressed_bytes, :checksum_sha256
                    )
                    """
                ),
                {
                    "session_id": session_id,
                    "consultation_id": consultation_id,
                    "segment_count": len(segments),
                    "archive_key": archive_key,
                    "compressed_bytes": len(compressed),
                    "checksum_sha256": digest,
                },
            )

            db.execute(
                delete(TranscriptSegment).where(
                    TranscriptSegment.session_id == session_id
                )
            )
            db.commit()

            archived_sessions += 1
            deleted_segments += len(segments)
            logger.info(
                "Archived transcript segments session_id=%s count=%s bytes=%s",
                session_id,
                len(segments),
                len(compressed),
            )

        return {
            "archived_sessions": archived_sessions,
            "deleted_segments": deleted_segments,
            "cutoff": cutoff.isoformat(),
        }
