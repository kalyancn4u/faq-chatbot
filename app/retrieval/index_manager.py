"""FAISS index lifecycle management and the FAISS <-> SQLite id mapping.

The FAISS index is a **derived artifact**: it can always be rebuilt from the
active rows of the ``faqs`` table, which is the system of record. This module
owns everything that keeps the two consistent:

- **The mapping.** FAISS returns row *positions* (0, 1, 2, ...). We persist a
  parallel list ``faq_ids`` where ``faq_ids[position]`` is the SQLite FAQ id, so
  a search result can be traced back to an authoritative record. The list is
  stored alongside the index together with the model name and dimension.
- **Rebuild.** Read active FAQs -> embed their questions -> build index -> write
  mapping -> **validate** -> atomically replace the old files. If validation
  fails, nothing is published, so we never leave an inconsistent index in place.
- **Validation invariant:** ``index.ntotal == len(faq_ids) == #active FAQs``.
- **Staleness.** The index is stale if it is missing, was built with a different
  model, or no longer matches the current set of active FAQ ids.

For V1 we always do a *full* rebuild on change. For a small-to-medium FAQ set
this is simple, correct, and fast — preferable to incremental add/remove
bookkeeping that is easy to get subtly wrong.
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from pathlib import Path

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.database.repository import FAQRepository
from app.embeddings.embedder import Embedder, get_embedder
from app.retrieval import faiss_index

logger = get_logger(__name__)


class IndexNotBuiltError(RuntimeError):
    """Raised when a search is attempted before any index exists on disk."""


class IndexConsistencyError(RuntimeError):
    """Raised when a freshly built index fails its validation invariant."""


@dataclass(frozen=True)
class RebuildResult:
    """Outcome of a rebuild."""

    faq_count: int
    dimension: int
    model_name: str


@dataclass(frozen=True)
class IndexStatus:
    """Snapshot of index health for the admin view."""

    exists: bool
    is_stale: bool
    indexed_vectors: int
    mapped_ids: int
    active_faqs: int
    model_name: str | None
    dimension: int | None


class IndexManager:
    """Builds, persists, validates, loads, and searches the FAISS index."""

    def __init__(
        self,
        embedder: Embedder | None = None,
        index_path: Path | None = None,
        id_map_path: Path | None = None,
    ) -> None:
        self._embedder = embedder or get_embedder()
        self._index_path = index_path or settings.index_path
        self._id_map_path = id_map_path or settings.id_map_path
        # Lazily loaded in-memory state.
        self._index = None
        self._faq_ids: list[int] | None = None
        self._loaded_model: str | None = None

    # --------------------------------------------------------------------- #
    # Build
    # --------------------------------------------------------------------- #
    def rebuild(self, conn) -> RebuildResult:
        """Rebuild the index from all active FAQs and atomically publish it.

        Args:
            conn: An open SQLite connection to read active FAQs from.

        Returns:
            A :class:`RebuildResult` describing the new index.

        Raises:
            ValueError: if there are no active FAQs to index.
            IndexConsistencyError: if the built index fails validation.
        """
        faqs = FAQRepository(conn).list_active()
        if not faqs:
            raise ValueError("Cannot build index: there are no active FAQs.")

        faq_ids = [f.id for f in faqs]
        questions = [f.question for f in faqs]

        logger.info("Rebuilding index for %d active FAQs...", len(faqs))
        embeddings = self._embedder.encode(questions)
        index = faiss_index.build_index(embeddings)

        # Validate BEFORE publishing anything.
        self._validate(index.ntotal, len(faq_ids), expected_active=len(faqs))

        dim = int(embeddings.shape[1])
        self._atomic_write(index, faq_ids, dim)

        # Refresh in-memory state so searches work immediately.
        self._index = index
        self._faq_ids = faq_ids
        self._loaded_model = self._embedder.model_name
        logger.info("Index rebuilt and published: %d vectors, dim=%d.", index.ntotal, dim)
        return RebuildResult(faq_count=len(faqs), dimension=dim, model_name=self._embedder.model_name)

    @staticmethod
    def _validate(indexed: int, mapped: int, expected_active: int) -> None:
        if not (indexed == mapped == expected_active):
            raise IndexConsistencyError(
                "Index consistency check failed: "
                f"indexed_vectors={indexed}, mapped_ids={mapped}, active_faqs={expected_active}."
            )

    def _atomic_write(self, index, faq_ids: list[int], dim: int) -> None:
        """Write index + mapping to temp files, then atomically move into place."""
        self._index_path.parent.mkdir(parents=True, exist_ok=True)
        tmp_index = self._index_path.with_suffix(self._index_path.suffix + ".tmp")
        tmp_map = self._id_map_path.with_suffix(self._id_map_path.suffix + ".tmp")

        faiss_index.save_index(index, tmp_index)
        payload = {"model": self._embedder.model_name, "dimension": dim, "faq_ids": faq_ids}
        tmp_map.write_text(json.dumps(payload), encoding="utf-8")

        # os.replace is atomic on the same filesystem and overwrites the target.
        os.replace(tmp_index, self._index_path)
        os.replace(tmp_map, self._id_map_path)

    # --------------------------------------------------------------------- #
    # Load
    # --------------------------------------------------------------------- #
    def exists(self) -> bool:
        """True if both index artifacts are present on disk."""
        return self._index_path.is_file() and self._id_map_path.is_file()

    def load(self) -> bool:
        """Load index + mapping into memory. Returns False if artifacts are missing."""
        if not self.exists():
            return False
        index = faiss_index.load_index(self._index_path)
        payload = json.loads(self._id_map_path.read_text(encoding="utf-8"))
        faq_ids = [int(i) for i in payload.get("faq_ids", [])]

        # Guard against a half-written/corrupt pair.
        self._validate_loaded(index.ntotal, len(faq_ids))
        self._index = index
        self._faq_ids = faq_ids
        self._loaded_model = payload.get("model")
        return True

    @staticmethod
    def _validate_loaded(indexed: int, mapped: int) -> None:
        if indexed != mapped:
            raise IndexConsistencyError(
                f"Loaded index is inconsistent: {indexed} vectors but {mapped} mapped ids. "
                "Rebuild the index."
            )

    def _ensure_loaded(self) -> None:
        if self._index is None and not self.load():
            raise IndexNotBuiltError(
                "No FAISS index found. Build it first (Admin > Rebuild index, or "
                "scripts/rebuild_index.py)."
            )

    # --------------------------------------------------------------------- #
    # Staleness / status
    # --------------------------------------------------------------------- #
    def is_stale(self, conn) -> bool:
        """True if the on-disk index no longer reflects the active FAQ set/model."""
        if not self.exists():
            return True
        try:
            payload = json.loads(self._id_map_path.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            return True

        if payload.get("model") != self._embedder.model_name:
            return True

        mapped_ids = sorted(int(i) for i in payload.get("faq_ids", []))
        active_ids = sorted(f.id for f in FAQRepository(conn).list_active())
        return mapped_ids != active_ids

    def status(self, conn) -> IndexStatus:
        """Return a health snapshot for the admin view."""
        active = FAQRepository(conn).count_active()
        if not self.exists():
            return IndexStatus(False, True, 0, 0, active, None, None)
        try:
            payload = json.loads(self._id_map_path.read_text(encoding="utf-8"))
            index = self._index if self._index is not None else faiss_index.load_index(self._index_path)
            mapped = len(payload.get("faq_ids", []))
            return IndexStatus(
                exists=True,
                is_stale=self.is_stale(conn),
                indexed_vectors=index.ntotal,
                mapped_ids=mapped,
                active_faqs=active,
                model_name=payload.get("model"),
                dimension=payload.get("dimension"),
            )
        except (json.JSONDecodeError, OSError, IndexConsistencyError):
            return IndexStatus(True, True, 0, 0, active, None, None)

    # --------------------------------------------------------------------- #
    # Search
    # --------------------------------------------------------------------- #
    def search(self, query: str, top_k: int | None = None) -> list[tuple[int, float]]:
        """Return up to ``top_k`` ``(faq_id, cosine_score)`` pairs, best first.

        Raises:
            IndexNotBuiltError: if no index exists yet.
        """
        self._ensure_loaded()
        assert self._index is not None and self._faq_ids is not None  # for type-checkers

        k = top_k if top_k is not None else settings.top_k
        query_vec = self._embedder.encode_one(query)
        scores, positions = faiss_index.search(self._index, query_vec, k)

        hits: list[tuple[int, float]] = []
        for pos, score in zip(positions[0], scores[0]):
            if pos == -1:  # empty slot (index smaller than k)
                continue
            hits.append((self._faq_ids[int(pos)], float(score)))
        return hits
