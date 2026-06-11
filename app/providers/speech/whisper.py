from app.providers.speech.base import SpeechToTextProvider, TranscriptionResult


class WhisperProvider(SpeechToTextProvider):
    """Future provider — not implemented in v1."""

    @property
    def provider_name(self) -> str:
        return "whisper"

    def transcribe_chunk(
        self,
        audio_bytes: bytes,
        *,
        mime_type: str,
        language: str | None = None,
    ) -> TranscriptionResult:
        raise NotImplementedError("WhisperProvider is not implemented yet")
