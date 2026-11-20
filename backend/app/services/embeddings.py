"""Embedding and vector similarity service using sentence-transformers.

Loads the local all-MiniLM-L6-v2 model on CPU once at startup, caches computed
embeddings in-memory, and provides fast deterministic cosine similarity calculations.
"""


import numpy as np
from sentence_transformers import SentenceTransformer

from app.config import get_settings

settings = get_settings()


class EmbeddingService:
    """Offline embedding generator and similarity calculator with in-memory caching."""

    def __init__(self, model_name: str | None = None):
        self.model_name = model_name or settings.embedding_model_name
        self._model = SentenceTransformer(self.model_name)
        self._cache: dict[str, np.ndarray] = {}

    def get_embedding(self, text: str) -> np.ndarray:
        """Get or compute normalized embedding vector for a single string."""
        text_clean = text.strip()
        if not text_clean:
            # Return zero vector if empty string
            dim = self._model.get_sentence_embedding_dimension() or 384
            return np.zeros(dim, dtype=np.float32)

        if text_clean in self._cache:
            return self._cache[text_clean]

        # normalize_embeddings=True ensures L2 norm is 1.0 (cosine sim = dot product)
        emb = self._model.encode(
            text_clean,
            normalize_embeddings=True,
            show_progress_bar=False,
            convert_to_numpy=True,
        )
        self._cache[text_clean] = emb
        return emb

    def get_embeddings_batch(self, texts: list[str]) -> list[np.ndarray]:
        """Compute embeddings for a list of strings using caching."""
        results: list[np.ndarray] = []
        uncached_indices: list[int] = []
        uncached_texts: list[str] = []

        for idx, text in enumerate(texts):
            clean = text.strip()
            if clean in self._cache:
                results.append(self._cache[clean])
            else:
                results.append(np.array([]))  # Placeholder
                uncached_indices.append(idx)
                uncached_texts.append(clean)

        if uncached_texts:
            encoded = self._model.encode(
                uncached_texts,
                normalize_embeddings=True,
                show_progress_bar=False,
                convert_to_numpy=True,
            )
            for idx, text, emb in zip(uncached_indices, uncached_texts, encoded, strict=True):
                self._cache[text] = emb
                results[idx] = emb

        return results

    def cosine_similarity(self, vec1: np.ndarray, vec2: np.ndarray) -> float:
        """Calculate cosine similarity between two normalized vectors."""
        if vec1.size == 0 or vec2.size == 0:
            return 0.0
        norm1 = np.linalg.norm(vec1)
        norm2 = np.linalg.norm(vec2)
        if norm1 == 0 or norm2 == 0:
            return 0.0
        dot = float(np.dot(vec1, vec2) / (norm1 * norm2))
        # Clip to [-1.0, 1.0] to account for tiny float inaccuracies
        return max(-1.0, min(1.0, dot))

    def similarity(self, text1: str, text2: str) -> float:
        """Calculate cosine similarity directly between two texts."""
        v1 = self.get_embedding(text1)
        v2 = self.get_embedding(text2)
        return self.cosine_similarity(v1, v2)

    def clear_cache(self) -> None:
        """Clear cached embeddings."""
        self._cache.clear()


_embedding_service_instance: EmbeddingService | None = None


def get_embedding_service() -> EmbeddingService:
    """Return singleton instance of EmbeddingService."""
    global _embedding_service_instance
    if _embedding_service_instance is None:
        _embedding_service_instance = EmbeddingService()
    return _embedding_service_instance
