from app.core.config import settings
from app.providers.speech.base import SpeechToTextProvider
from app.providers.speech.sarvam import SarvamProvider

_stt_provider: SpeechToTextProvider | None = None


def get_speech_to_text_provider() -> SpeechToTextProvider:
    global _stt_provider

    if _stt_provider is not None:
        return _stt_provider

    provider = settings.STT_PROVIDER.lower()

    if provider == "sarvam":
        _stt_provider = SarvamProvider()
        return _stt_provider

    raise ValueError(f"Unsupported STT provider: {settings.STT_PROVIDER}")
