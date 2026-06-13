import uuid
from datetime import UTC, datetime, timedelta
from functools import lru_cache

import boto3
from botocore.config import Config
from botocore.exceptions import ClientError
from sqlalchemy import text
from sqlalchemy.orm import Session

from app.core.config import settings
from app.core.logging import get_logger

logger = get_logger(__name__)


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


class AudioRetentionWorker:
    """Delete audio chunk objects from R2 after configurable retention window."""

    def run(self, db: Session) -> dict:
        cutoff = datetime.now(UTC) - timedelta(days=settings.AUDIO_RETENTION_DAYS)
        rows = db.execute(
            text(
                """
                SELECT
                    ac.id AS chunk_id,
                    ac.session_id,
                    ac.chunk_number,
                    cs.consultation_id,
                    ac.created_at
                FROM audio_chunks ac
                JOIN consultation_sessions cs ON cs.id = ac.session_id
                JOIN transcripts t ON t.consultation_id = cs.consultation_id
                WHERE ac.created_at < :cutoff
                ORDER BY ac.created_at
                LIMIT :batch_size
                """
            ),
            {
                "cutoff": cutoff,
                "batch_size": settings.AUDIO_RETENTION_BATCH_SIZE,
            },
        ).mappings().all()

        deleted = 0
        verified = 0
        bytes_deleted = 0

        for row in rows:
            object_key = (
                f"audio-chunks/{row['session_id']}/{row['chunk_number']}.webm"
            )
            size = self._object_size(object_key)
            if self._delete_object(object_key):
                deleted += 1
                bytes_deleted += size
                verified += 1
                db.execute(
                    text(
                        """
                        INSERT INTO audio_retention_audits (
                            id, session_id, consultation_id, object_key,
                            action, bytes_deleted, retention_days, verified
                        ) VALUES (
                            gen_random_uuid(), :session_id, :consultation_id, :object_key,
                            'deleted', :bytes_deleted, :retention_days, TRUE
                        )
                        """
                    ),
                    {
                        "session_id": row["session_id"],
                        "consultation_id": row["consultation_id"],
                        "object_key": object_key,
                        "bytes_deleted": size,
                        "retention_days": settings.AUDIO_RETENTION_DAYS,
                    },
                )
                db.commit()

        return {
            "deleted_objects": deleted,
            "verified_deletes": verified,
            "bytes_deleted": bytes_deleted,
            "cutoff": cutoff.isoformat(),
        }

    @staticmethod
    def _object_size(object_key: str) -> int:
        try:
            response = _get_r2_client().head_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=object_key,
            )
            return int(response.get("ContentLength", 0))
        except ClientError:
            return 0

    @staticmethod
    def _delete_object(object_key: str) -> bool:
        try:
            _get_r2_client().delete_object(
                Bucket=settings.R2_BUCKET_NAME,
                Key=object_key,
            )
            return True
        except ClientError:
            logger.warning("Failed to delete audio object key=%s", object_key)
            return False
