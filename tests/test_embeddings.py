"""Tests for embedding generation (uses the real model via the session fixture)."""

from __future__ import annotations

import numpy as np
import pytest


def test_encode_shape_and_dtype(embedder):
    vectors = embedder.encode(["hello world", "another sentence"])
    assert vectors.shape == (2, embedder.dimension)
    assert vectors.dtype == np.float32


def test_embeddings_are_normalized(embedder):
    # L2 norm should be ~1 for every row (so inner product == cosine).
    vectors = embedder.encode(["reset my password", "track my order"])
    norms = np.linalg.norm(vectors, axis=1)
    assert np.allclose(norms, 1.0, atol=1e-3)


def test_paraphrases_are_more_similar_than_unrelated(embedder):
    v = embedder.encode(
        [
            "How do I reset my password?",
            "I forgot my password.",
            "How long does shipping take?",
        ]
    )
    sim_paraphrase = float(v[0] @ v[1])
    sim_unrelated = float(v[0] @ v[2])
    assert sim_paraphrase > sim_unrelated


def test_encode_empty_raises(embedder):
    with pytest.raises(ValueError):
        embedder.encode([])


def test_encode_one_is_2d(embedder):
    vec = embedder.encode_one("single query")
    assert vec.shape == (1, embedder.dimension)
