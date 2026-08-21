"""Tests for the FAQ answering service and feedback service."""

from __future__ import annotations

from app.retrieval.search import SemanticSearch
from app.services.faq_service import AnswerStatus, ConfidenceLevel, FAQService
from app.services.feedback_service import FeedbackService


def _service(built_index, conn) -> FAQService:
    return FAQService(conn, search=SemanticSearch(index_manager=built_index))


def test_answer_found_for_paraphrase(built_index, seeded_conn):
    result = _service(built_index, seeded_conn).answer_question(
        "I can't remember my login password"
    )
    assert result.status is AnswerStatus.ANSWER_FOUND
    assert result.confidence_level in (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM)
    assert "password" in result.matched_question.lower()
    assert result.answer  # a curated answer, not the fallback


def test_low_confidence_returns_fallback_and_logs(built_index, seeded_conn):
    service = _service(built_index, seeded_conn)
    result = service.answer_question("quantum chromodynamics lecture notes")
    assert result.status in (AnswerStatus.LOW_CONFIDENCE, AnswerStatus.NO_MATCH)
    assert result.confidence_level in (ConfidenceLevel.LOW, ConfidenceLevel.NONE)
    # The weak match is NOT presented as an authoritative answer.
    assert "couldn't find" in result.answer.lower()
    # And the question was logged for admin review.
    logged = seeded_conn.execute(
        "SELECT COUNT(*) AS n FROM unanswered_questions"
    ).fetchone()["n"]
    assert logged == 1


def test_empty_question_is_error(built_index, seeded_conn):
    result = _service(built_index, seeded_conn).answer_question("   ")
    assert result.status is AnswerStatus.ERROR


def test_missing_index_is_error_not_crash(index_manager, seeded_conn):
    # index_manager here was never rebuilt -> no artifacts on disk.
    service = FAQService(seeded_conn, search=SemanticSearch(index_manager=index_manager))
    result = service.answer_question("reset my password")
    assert result.status is AnswerStatus.ERROR


def test_alternatives_are_populated(built_index, seeded_conn):
    result = _service(built_index, seeded_conn).answer_question("reset my password")
    assert result.status is AnswerStatus.ANSWER_FOUND
    assert len(result.alternative_matches) >= 1
    assert result.matched_faq_id not in {a.faq_id for a in result.alternative_matches}


def test_feedback_service_records(seeded_conn):
    fb = FeedbackService(seeded_conn)
    fid = fb.record("was this helpful?", faq_id=1, similarity_score=0.8, was_helpful=True)
    assert fid > 0
    assert fb.recent()[0].was_helpful is True
