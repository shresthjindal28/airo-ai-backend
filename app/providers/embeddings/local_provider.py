import logging
import os
import threading

from sentence_transformers import SentenceTransformer

from app.core.config import settings
from app.providers.embeddings.base import EmbeddingProvider

logger = logging.getLogger(__name__)

FALLBACK_MODEL = "intfloat/e5-small-v2"
BGE_QUERY_PREFIX = "Represent this sentence for searching relevant passages: "

_model_lock = threading.Lock()
_model_instance: SentenceTransformer | None = None
_loaded_model_name: str | None = None


def _apply_hf_token() -> None:
    if settings.HF_TOKEN:
        os.environ["HF_TOKEN"] = settings.HF_TOKEN
        os.environ["HUGGING_FACE_HUB_TOKEN"] = settings.HF_TOKEN


def preload_embedding_model(model_name: str | None = None) -> None:
    _apply_hf_token()
    name = model_name or settings.EMBEDDING_MODEL
    _get_model(name)
    logger.info("Embedding model preloaded model=%s", name)


def _get_model(model_name: str) -> SentenceTransformer:
    global _model_instance, _loaded_model_name

    with _model_lock:
        if _model_instance is not None and _loaded_model_name == model_name:
            return _model_instance

        try:
            logger.info("Loading sentence-transformers model=%s", model_name)
            _model_instance = SentenceTransformer(model_name)
            _loaded_model_name = model_name
            return _model_instance
        except Exception as exc:
            if model_name == FALLBACK_MODEL:
                raise RuntimeError(
                    f"Failed to load embedding model {model_name}"
                ) from exc
            logger.warning(
                "Primary model %s failed (%s); falling back to %s",
                model_name,
                exc,
                FALLBACK_MODEL,
            )
            _model_instance = SentenceTransformer(FALLBACK_MODEL)
            _loaded_model_name = FALLBACK_MODEL
            return _model_instance


class LocalEmbeddingProvider(EmbeddingProvider):

    def __init__(
        self,
        *,
        model_name: str | None = None,
        dimensions: int | None = None,
    ) -> None:
        self._model_name = model_name or settings.EMBEDDING_MODEL
        self._dimensions = dimensions or settings.EMBEDDING_DIMENSIONS
        self._model = _get_model(self._model_name)

    @property
    def dimensions(self) -> int:
        return self._dimensions

    def embed_text(self, text: str, *, is_query: bool = False) -> list[float]:
        if not text.strip():
            return [0.0] * self._dimensions
        prepared = self._prepare_text(text, is_query=is_query)
        vector = self._model.encode(
            prepared,
            normalize_embeddings=True,
            show_progress_bar=False,
        )
        return vector.tolist()

    def embed_batch(
        self,
        texts: list[str],
        *,
        is_query: bool = False,
    ) -> list[list[float]]:
        if not texts:
            return []
        prepared = [self._prepare_text(t, is_query=is_query) for t in texts]
        vectors = self._model.encode(
            prepared,
            normalize_embeddings=True,
            show_progress_bar=False,
            batch_size=32,
        )
        return [vector.tolist() for vector in vectors]

    @staticmethod
    def _prepare_text(text: str, *, is_query: bool) -> str:
        cleaned = text.strip()
        if is_query and "bge" in settings.EMBEDDING_MODEL.lower():
            return f"{BGE_QUERY_PREFIX}{cleaned}"
        return cleaned
