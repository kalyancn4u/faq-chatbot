"""Feedback service — thin orchestration over the feedback repository.

Kept separate from :mod:`faq_service` because recording "was this helpful?" is a
distinct concern from answering, and the UI calls it at a different moment (after
the user reacts). In V1 feedback is only *stored*; nothing retrains automatically
from it. The stored rows (question, matched FAQ, score, helpfulness) are the raw
material for later tuning of coverage and thresholds.
"""

from __future__ import annotations

import sqlite3

from app.database.repository import Feedback, FeedbackRepository


class FeedbackService:
    """Record and read user feedback."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._repo = FeedbackRepository(conn)

    def record(
        self,
        user_question: str,
        faq_id: int | None,
        similarity_score: float | None,
        was_helpful: bool,
    ) -> int:
        """Store one helpfulness signal and return its id."""
        return self._repo.add(
            user_question=user_question,
            faq_id=faq_id,
            similarity_score=similarity_score,
            was_helpful=was_helpful,
        )

    def recent(self, limit: int = 100) -> list[Feedback]:
        """Most recent feedback first (for the admin view)."""
        return self._repo.list_recent(limit=limit)
