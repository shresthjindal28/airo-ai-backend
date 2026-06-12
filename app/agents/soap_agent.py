from app.providers.llm.base import SoapNoteContent
from app.providers.llm.huggingface_provider import HuggingFaceLLMProvider


class SoapAgent:
    """Generates structured SOAP notes from consultation transcripts."""

    def __init__(self, provider: HuggingFaceLLMProvider | None = None) -> None:
        self._provider = provider or HuggingFaceLLMProvider()

    def generate(
        self,
        *,
        transcript: str,
        chief_complaint: str | None = None,
    ) -> SoapNoteContent:
        return self._provider.generate_soap_note(
            transcript=transcript,
            chief_complaint=chief_complaint,
        )
