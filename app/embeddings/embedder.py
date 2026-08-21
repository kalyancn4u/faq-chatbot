"""Sentence embedding generation.

An *embedding* is a fixed-length vector of numbers that captures the meaning of a
piece of text: sentences with similar meaning map to nearby vectors. That is what
lets "I forgot my password" and "how do I reset my password?" match even though
they share few words.

This module wraps :class:`sentence_transformers.SentenceTransformer` with three
concerns handled for the rest of the app:

1. **Model caching** — the model is loaded once per process (loading is the slow
   part, a few seconds) and reused, keyed by model name.
2. **CPU + normalization** — vectors are L2-normalized so that a dot product
   equals cosine similarity, which is what the FAISS index (Phase 4) relies on.
3. **Stable dtype/shape** — always returns a ``float32`` array of shape
   ``(n_texts, dim)``, the format FAISS expects.

The model name comes from central configuration, so switching to a multilingual
model is a one-line config change, not a code change.
"""

from __future__ import annotations

from functools import lru_cache

import numpy as np

from app.config.logging_config import get_logger
from app.config.settings import settings

logger = get_logger(__name__)


@lru_cache(maxsize=2)
def _load_model(model_name: str):
    """Load and cache a SentenceTransformer on CPU (one instance per name).

    Imported lazily so that importing this module (e.g. in tests that don't
    embed) does not pull in torch/sentence-transformers.
    """
    from sentence_transformers import SentenceTransformer

    logger.info("Loading embedding model %r (first load may take a few seconds)...", model_name)
    model = SentenceTransformer(model_name, device="cpu")
    logger.info("Embedding model %r ready (dim=%d).", model_name, model.get_sentence_embedding_dimension())
    return model


class Embedder:
    """Turns text into normalized embedding vectors.

    Args:
        model_name: sentence-transformers model id. Defaults to the configured
            ``EMBEDDING_MODEL_NAME``.
    """

    def __init__(self, model_name: str | None = None) -> None:
        self.model_name = model_name or settings.embedding_model_name

    @property
    def dimension(self) -> int:
        """The embedding vector length for the configured model."""
        return int(_load_model(self.model_name).get_sentence_embedding_dimension())

    def encode(self, texts: list[str], batch_size: int = 32) -> np.ndarray:
        """Embed a list of texts.

        Args:
            texts: Non-empty list of strings to embed.
            batch_size: How many texts to encode per forward pass.

        Returns:
            A ``float32`` array of shape ``(len(texts), dimension)`` whose rows are
            L2-normalized (so dot product == cosine similarity).

        Raises:
            ValueError: if ``texts`` is empty.
        """
        if not texts:
            raise ValueError("encode() requires at least one text.")

        model = _load_model(self.model_name)
        vectors = model.encode(
            texts,
            batch_size=batch_size,
            convert_to_numpy=True,
            normalize_embeddings=True,  # unit vectors -> inner product is cosine
            show_progress_bar=False,
        )
        return np.asarray(vectors, dtype=np.float32)

    def encode_one(self, text: str) -> np.ndarray:
        """Embed a single string, returning a ``(1, dimension)`` array.

        Kept 2-D so it can be passed straight to FAISS search without reshaping.
        """
        return self.encode([text])


@lru_cache(maxsize=1)
def get_embedder() -> Embedder:
    """Return a process-wide shared Embedder for the configured model."""
    return Embedder()
