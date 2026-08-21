"""Tests for FAISS index build, persistence, mapping, and consistency."""

from __future__ import annotations

import pytest

from app.database.repository import FAQRepository
from app.retrieval.index_manager import (
    IndexConsistencyError,
    IndexManager,
    IndexNotBuiltError,
)


def test_rebuild_creates_consistent_artifacts(index_manager, seeded_conn):
    result = index_manager.rebuild(seeded_conn)
    active = FAQRepository(seeded_conn).count_active()
    assert result.faq_count == active
    assert index_manager.exists()
    # Invariant: indexed vectors == mapped ids == active FAQs.
    status = index_manager.status(seeded_conn)
    assert status.indexed_vectors == status.mapped_ids == active


def test_rebuild_with_no_active_faqs_raises(index_manager, conn):
    with pytest.raises(ValueError):
        index_manager.rebuild(conn)


def test_search_maps_positions_to_faq_ids(built_index, seeded_conn):
    hits = built_index.search("I can't remember my password", top_k=3)
    assert hits
    top_faq_id, top_score = hits[0]
    faq = FAQRepository(seeded_conn).get(top_faq_id)
    assert faq is not None
    assert "password" in faq.question.lower()
    assert -1.0 <= top_score <= 1.0


def test_search_without_index_raises(index_manager):
    with pytest.raises(IndexNotBuiltError):
        index_manager.search("anything")


def test_load_after_rebuild(index_manager, seeded_conn, embedder, tmp_path):
    index_manager.rebuild(seeded_conn)
    # A brand-new manager pointed at the same files should load them.
    fresh = IndexManager(
        embedder=embedder,
        index_path=tmp_path / "faq.faiss",
        id_map_path=tmp_path / "id_map.json",
    )
    assert fresh.load() is True
    assert fresh.search("reset password", top_k=1)


def test_is_stale_detects_new_faq(built_index, seeded_conn):
    assert built_index.is_stale(seeded_conn) is False
    FAQRepository(seeded_conn).add("A brand new question?", "An answer.")
    seeded_conn.commit()
    assert built_index.is_stale(seeded_conn) is True


def test_is_stale_detects_deactivation(built_index, seeded_conn):
    first_id = FAQRepository(seeded_conn).list_active()[0].id
    FAQRepository(seeded_conn).set_active(first_id, False)
    seeded_conn.commit()
    assert built_index.is_stale(seeded_conn) is True


def test_corrupt_id_map_detected_on_load(index_manager, seeded_conn):
    index_manager.rebuild(seeded_conn)
    # Corrupt the mapping so it no longer matches the index vector count.
    index_manager._id_map_path.write_text('{"model": "x", "faq_ids": [1]}', encoding="utf-8")
    fresh = IndexManager(
        embedder=index_manager._embedder,
        index_path=index_manager._index_path,
        id_map_path=index_manager._id_map_path,
    )
    with pytest.raises(IndexConsistencyError):
        fresh.load()
