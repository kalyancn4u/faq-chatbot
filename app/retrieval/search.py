"""Semantic search: turn a query into ranked FAQ candidates.

This sits one level above :class:`~app.retrieval.index_manager.IndexManager`. The
index manager returns bare ``(faq_id, score)`` pairs; here we join those ids back
to their **authoritative** SQLite records so callers get full FAQ content to work
with. Confidence/fallback decisions happen a level up again, in the service layer
— this module only ranks and hydrates.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass

from app.database.repository import FAQRepository
from app.retrieval.index_manager import IndexManager


@dataclass(frozen=True)
class SearchCandidate:
    """One ranked FAQ match with its authoritative content and score."""

    faq_id: int
    question: str
    answer: str
    category: str
    score: float  # cosine similarity in [-1, 1]


class SemanticSearch:
    """Rank active FAQs by semantic similarity to a query."""

    def __init__(self, index_manager: IndexManager | None = None) -> None:
        self._index = index_manager or IndexManager()

    def search(
        self, conn: sqlite3.Connection, query: str, top_k: int | None = None
    ) -> list[SearchCandidate]:
        """Return ranked candidates (best first) hydrated from SQLite.

        Ids returned by FAISS but missing/inactive in SQLite are skipped, so a
        stale index can never surface a deleted answer.

        Raises:
            IndexNotBuiltError: if no index exists (propagated from the manager).
        """
        hits = self._index.search(query, top_k=top_k)
        repo = FAQRepository(conn)

        candidates: list[SearchCandidate] = []
        for faq_id, score in hits:
            faq = repo.get(faq_id)
            if faq is None or not faq.is_active:
                continue
            candidates.append(
                SearchCandidate(
                    faq_id=faq.id,
                    question=faq.question,
                    answer=faq.answer,
                    category=faq.category,
                    score=score,
                )
            )
        return candidates
