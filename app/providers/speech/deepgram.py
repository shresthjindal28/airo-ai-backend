from app.providers.speech.base import SpeechToTextProvider, TranscriptionResult


class DeepgramProvider(SpeechToTextProvider):
    """Future provider — not implemented in v1."""

    @property
    def provider_name(self) -> str:
        return "deepgram"

    def transcribe_chunk(
        self,
        audio_bytes: bytes,
        *,
        mime_type: str,
        language: str | None = None,
    ) -> TranscriptionResult:
        raise NotImplementedError("DeepgramProvider is not implemented yet")
