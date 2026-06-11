from abc import ABC, abstractmethod


class EmbeddingProvider(ABC):

    @property
    @abstractmethod
    def dimensions(self) -> int:
        pass

    @abstractmethod
    def embed_text(self, text: str, *, is_query: bool = False) -> list[float]:
        pass

    @abstractmethod
    def embed_batch(
        self,
        texts: list[str],
        *,
        is_query: bool = False,
    ) -> list[list[float]]:
        pass
