"""Tests for semantic search hydration (ids -> authoritative FAQ content)."""

from __future__ import annotations

from app.database.repository import FAQRepository
from app.retrieval.search import SemanticSearch


def test_semantic_search_returns_hydrated_candidates(built_index, seeded_conn):
    search = SemanticSearch(index_manager=built_index)
    results = search.search(seeded_conn, "I can't remember my login password", top_k=3)
    assert results
    top = results[0]
    assert "password" in top.question.lower()
    assert top.answer  # authoritative answer text is populated
    assert -1.0 <= top.score <= 1.0
    # Ranked descending by score.
    scores = [c.score for c in results]
    assert scores == sorted(scores, reverse=True)


def test_semantic_search_skips_deactivated_faqs(built_index, seeded_conn):
    # Deactivate the best password match; a stale index must not surface it.
    repo = FAQRepository(seeded_conn)
    for faq in repo.list_active():
        if "reset my password" in faq.question.lower():
            repo.set_active(faq.id, False)
    seeded_conn.commit()

    search = SemanticSearch(index_manager=built_index)
    results = search.search(seeded_conn, "reset my password", top_k=5)
    returned_ids = {c.faq_id for c in results}
    deactivated = {
        f.id for f in repo.list_all(include_inactive=True) if not f.is_active
    }
    assert returned_ids.isdisjoint(deactivated)


def test_unrelated_query_scores_low(built_index, seeded_conn):
    search = SemanticSearch(index_manager=built_index)
    results = search.search(seeded_conn, "quantum chromodynamics lecture notes", top_k=1)
    # There is always a nearest neighbour, but it should be a weak match.
    assert results
    assert results[0].score < 0.45
