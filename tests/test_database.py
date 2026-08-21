"""Tests for schema, connection, and repository behavior."""

from __future__ import annotations

import pytest

from app.database.repository import (
    DuplicateFAQError,
    FAQRepository,
    FeedbackRepository,
    UnansweredRepository,
)


def test_schema_creates_tables(conn):
    names = {
        r["name"]
        for r in conn.execute("SELECT name FROM sqlite_master WHERE type='table'").fetchall()
    }
    assert {"faqs", "feedback", "unanswered_questions"} <= names


def test_add_and_get_roundtrip(conn):
    repo = FAQRepository(conn)
    faq_id = repo.add("Q?", "A.", category="Account", tags=["x", "y"])
    faq = repo.get(faq_id)
    assert faq is not None
    assert faq.question == "Q?"
    assert faq.answer == "A."
    assert faq.category == "Account"
    assert faq.tags == ["x", "y"]
    assert faq.is_active is True


def test_duplicate_question_rejected(conn):
    repo = FAQRepository(conn)
    repo.add("Same question?", "A1")
    with pytest.raises(DuplicateFAQError):
        repo.add("Same question?", "A2")


def test_empty_question_or_answer_rejected(conn):
    repo = FAQRepository(conn)
    with pytest.raises(ValueError):
        repo.add("   ", "answer")
    with pytest.raises(ValueError):
        repo.add("question", "")


def test_update_partial_fields(conn):
    repo = FAQRepository(conn)
    faq_id = repo.add("Q?", "A.", category="General")
    assert repo.update(faq_id, answer="new answer") is True
    faq = repo.get(faq_id)
    assert faq.answer == "new answer"
    assert faq.question == "Q?"  # unchanged


def test_soft_delete_excludes_from_active(conn):
    repo = FAQRepository(conn)
    faq_id = repo.add("Q?", "A.")
    assert repo.count_active() == 1
    repo.set_active(faq_id, False)
    assert repo.count_active() == 0
    assert repo.get(faq_id) is not None  # still present, just inactive


def test_hard_delete_cascades_feedback(conn):
    faqs = FAQRepository(conn)
    fb = FeedbackRepository(conn)
    faq_id = faqs.add("Q?", "A.")
    fb.add("user q", faq_id, 0.9, True)
    faqs.delete(faq_id)
    remaining = conn.execute("SELECT COUNT(*) AS n FROM feedback").fetchone()["n"]
    assert remaining == 0  # cascade removed the feedback row


def test_search_matches_question_and_answer(seeded_conn):
    repo = FAQRepository(seeded_conn)
    assert len(repo.search("password")) >= 2
    assert repo.search("PayPal")  # matches an answer


def test_list_categories(seeded_conn):
    cats = FAQRepository(seeded_conn).list_categories()
    assert {"Account", "Billing", "Shipping", "General"} <= set(cats)


def test_feedback_storage(conn):
    fb = FeedbackRepository(conn)
    fb.add("why locked?", None, 0.3, False)
    recent = fb.list_recent()
    assert recent[0].was_helpful is False
    assert recent[0].similarity_score == pytest.approx(0.3)


def test_unanswered_log_and_review(conn):
    un = UnansweredRepository(conn)
    uid = un.log("do you sell rockets?", 0.1)
    assert len(un.list(only_unreviewed=True)) == 1
    assert un.mark_reviewed(uid) is True
    assert un.list(only_unreviewed=True) == []
