import json

import redis

from app.core.config import settings
from app.core.logging import get_logger
from app.schemas.transcript_event import TranscriptEvent

logger = get_logger(__name__)

TRANSCRIPT_EVENTS_CHANNEL = "airo:transcript:events"


class TranscriptEventPublisher:

    def __init__(self) -> None:
        self._client = redis.Redis.from_url(
            settings.REDIS_URL,
            decode_responses=True,
        )

    def publish(self, event: TranscriptEvent) -> None:
        payload = event.model_dump(mode="json")
        self._client.publish(TRANSCRIPT_EVENTS_CHANNEL, json.dumps(payload))
        logger.info(
            "Published transcript event type=%s session_id=%s",
            event.type,
            event.session_id,
        )
