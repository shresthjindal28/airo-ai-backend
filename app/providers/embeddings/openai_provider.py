from openai import OpenAI

from app.core.config import settings
from app.providers.embeddings.base import EmbeddingProvider


class OpenAIEmbeddingProvider(EmbeddingProvider):

    def __init__(
        self,
        *,
        api_key: str | None = None,
        model: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self._api_key = api_key or settings.OPENAI_API_KEY
        self._model = model or settings.EMBEDDING_MODEL
        self._dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
        self._client = OpenAI(api_key=self._api_key)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(self, text: str) -> list[float]:
        if not text.strip():
            return [0.0] * self._dimensions
        response = self._client.embeddings.create(
            input=text,
            model=self._model,
            dimensions=self._dimensions,
        )
        return list(response.data[0].embedding)

    def embed_batch(self, texts: list[str]) -> list[list[float]]:
        if not texts:
            return []
        response = self._client.embeddings.create(
            input=texts,
            model=self._model,
            dimensions=self._dimensions,
        )
        ordered = sorted(response.data, key=lambda item: item.index)
        return [list(item.embedding) for item in ordered]
