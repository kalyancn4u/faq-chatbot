"""Low-level FAISS operations (build / save / load / search).

This module knows *only* about vectors — not about SQLite, FAQ ids, or
confidence. Keeping it that thin makes it easy to reason about and test.

**Similarity metric.** We use :class:`faiss.IndexFlatIP` (exact, brute-force
inner-product search). Because embeddings are L2-normalized upstream (see
:mod:`app.embeddings.embedder`), the inner product equals **cosine similarity**,
which ranges from -1 to 1 (in practice ~0 to 1 for this model). ``Flat`` means no
approximation: for a small-to-medium FAQ set it is fast, exact, and has nothing
to tune — the right default. Approximate indexes (IVF/HNSW) only pay off at very
large scale and can be swapped in later behind this same interface.
"""

from __future__ import annotations

from pathlib import Path

import faiss
import numpy as np


def build_index(embeddings: np.ndarray) -> faiss.Index:
    """Build an exact cosine-similarity index from normalized embeddings.

    Args:
        embeddings: ``float32`` array of shape ``(n, dim)``, L2-normalized. Row
            order is preserved as FAISS positions ``0..n-1``.

    Returns:
        A populated ``IndexFlatIP``.

    Raises:
        ValueError: if the array is empty or not 2-D.
    """
    if embeddings.ndim != 2 or embeddings.shape[0] == 0:
        raise ValueError("build_index requires a non-empty 2-D (n, dim) array.")
    vectors = np.ascontiguousarray(embeddings, dtype=np.float32)
    index = faiss.IndexFlatIP(vectors.shape[1])
    index.add(vectors)
    return index


def save_index(index: faiss.Index, path: Path | str) -> None:
    """Serialize a FAISS index to disk (creating parent dirs)."""
    path = Path(path)
    path.parent.mkdir(parents=True, exist_ok=True)
    faiss.write_index(index, str(path))


def load_index(path: Path | str) -> faiss.Index:
    """Load a FAISS index from disk.

    Raises:
        FileNotFoundError: if the index file does not exist.
    """
    path = Path(path)
    if not path.is_file():
        raise FileNotFoundError(f"FAISS index not found: {path}")
    return faiss.read_index(str(path))


def search(
    index: faiss.Index, query_vectors: np.ndarray, top_k: int
) -> tuple[np.ndarray, np.ndarray]:
    """Search the index for the nearest rows to each query vector.

    Args:
        index: A populated FAISS index.
        query_vectors: ``float32`` array of shape ``(q, dim)``, normalized.
        top_k: Number of neighbours to return per query.

    Returns:
        ``(scores, positions)`` arrays of shape ``(q, k)``. ``positions`` are
        FAISS row indices; a value of ``-1`` marks an empty slot when the index
        holds fewer than ``top_k`` vectors. ``scores`` are cosine similarities.
    """
    queries = np.ascontiguousarray(query_vectors, dtype=np.float32)
    k = max(1, min(top_k, index.ntotal))
    scores, positions = index.search(queries, k)
    return scores, positions
