import io
import time

from sarvamai import SarvamAI

from app.core.config import settings
from app.core.logging import get_logger
from app.providers.speech.base import SpeechToTextProvider, TranscriptionResult

logger = get_logger(__name__)


class SarvamProvider(SpeechToTextProvider):

    def __init__(self) -> None:
        if not settings.SARVAM_API_KEY:
            raise ValueError("SARVAM_API_KEY is required for SarvamProvider")

        self._client = SarvamAI(api_subscription_key=settings.SARVAM_API_KEY)

    @property
    def provider_name(self) -> str:
        return "sarvam"

    def transcribe_chunk(
        self,
        audio_bytes: bytes,
        *,
        mime_type: str,
        language: str | None = None,
    ) -> TranscriptionResult:
        started = time.perf_counter()

        kwargs: dict = {
            "file": io.BytesIO(audio_bytes),
            "model": settings.SARVAM_MODEL,
            "mode": settings.SARVAM_MODE,
        }

        if language:
            kwargs["language_code"] = language

        response = self._client.speech_to_text.transcribe(**kwargs)

        text = getattr(response, "transcript", None) or str(response)
        confidence = getattr(response, "confidence", None)
        detected_language = getattr(response, "language_code", None) or language

        latency_ms = int((time.perf_counter() - started) * 1000)
        logger.info(
            "Sarvam transcription completed bytes=%s latency_ms=%s",
            len(audio_bytes),
            latency_ms,
        )

        return TranscriptionResult(
            text=text.strip(),
            confidence_score=float(confidence) if confidence is not None else None,
            language=detected_language,
        )
