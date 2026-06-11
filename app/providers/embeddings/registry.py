from functools import lru_cache

from app.core.config import settings
from app.providers.embeddings.base import EmbeddingProvider
from app.providers.embeddings.local_provider import LocalEmbeddingProvider


@lru_cache(maxsize=1)
def get_embedding_provider() -> EmbeddingProvider:
    provider = settings.EMBEDDING_PROVIDER.lower()
    if provider == "local":
        return LocalEmbeddingProvider()
    if provider == "openai":
        from app.providers.embeddings.openai_provider import OpenAIEmbeddingProvider

        return OpenAIEmbeddingProvider()
    raise ValueError(f"Unsupported embedding provider: {provider}")
