from functools import lru_cache

from app.core.config import settings
from app.providers.prescription.base import PrescriptionProvider
from app.providers.prescription.huggingface_provider import (
    HuggingFacePrescriptionProvider,
)
from app.providers.prescription.openai_provider import OpenAIPrescriptionProvider

_SUPPORTED = {
    "huggingface",
    "hf",
    "openai",
    "sarvam",
    "claude",
    "gemini",
    "local",
}


@lru_cache(maxsize=1)
def get_prescription_provider() -> PrescriptionProvider:
    provider = settings.PRESCRIPTION_PROVIDER.lower()

    if provider in {"huggingface", "hf"}:
        return HuggingFacePrescriptionProvider()

    if provider == "openai":
        return OpenAIPrescriptionProvider()

    if provider in {"sarvam", "claude", "gemini", "local"}:
        raise ValueError(
            f"Prescription provider '{provider}' is not implemented yet. "
            f"Use huggingface or openai."
        )

    raise ValueError(
        f"Unsupported prescription provider: {provider}. "
        f"Supported: {', '.join(sorted(_SUPPORTED))}"
    )
