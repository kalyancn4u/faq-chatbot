"""The FAQ answering service — the app's core decision logic.

``answer_question`` is the single entry point the UI calls. It runs the full
pipeline (validate -> search -> hydrate -> decide) and returns one structured
:class:`AnswerResult`. Crucially, it does **not** blindly return the nearest
match: two configurable thresholds split matches into three bands, and weak
matches yield an honest fallback instead of a possibly-wrong answer. This is what
keeps V1 from "hallucinating" — every returned answer is a curated FAQ that
cleared the confidence bar.

Confidence bands (cosine similarity ``s`` against ``settings``):

- ``s >= SIMILARITY_THRESHOLD_HIGH``          -> HIGH,   status ANSWER_FOUND
- ``SIMILARITY_THRESHOLD_LOW <= s < HIGH``    -> MEDIUM, status ANSWER_FOUND (with caveat)
- ``s < SIMILARITY_THRESHOLD_LOW``            -> LOW,    status LOW_CONFIDENCE (fallback)

Thresholds are empirical — tune them against your own FAQs and the feedback log;
the defaults are a starting point, not a universal truth.
"""

from __future__ import annotations

import sqlite3
from dataclasses import dataclass, field
from enum import Enum

from app.config.logging_config import get_logger
from app.config.settings import settings
from app.database.repository import UnansweredRepository
from app.retrieval.index_manager import IndexNotBuiltError
from app.retrieval.search import SearchCandidate, SemanticSearch

logger = get_logger(__name__)

FALLBACK_MESSAGE = (
    "I couldn't find a sufficiently reliable answer to your question. "
    "Try rephrasing it, or pick one of the suggested related topics."
)


class AnswerStatus(str, Enum):
    """Outcome of an answer attempt."""

    ANSWER_FOUND = "ANSWER_FOUND"
    LOW_CONFIDENCE = "LOW_CONFIDENCE"
    NO_MATCH = "NO_MATCH"
    ERROR = "ERROR"


class ConfidenceLevel(str, Enum):
    """Human-facing confidence band for a match."""

    HIGH = "High"
    MEDIUM = "Medium"
    LOW = "Low"
    NONE = "None"


@dataclass(frozen=True)
class AlternativeMatch:
    """A suggested related FAQ (not the primary answer)."""

    faq_id: int
    question: str
    score: float


@dataclass(frozen=True)
class AnswerResult:
    """Structured result of :meth:`FAQService.answer_question`."""

    user_question: str
    status: AnswerStatus
    answer: str
    confidence_level: ConfidenceLevel
    matched_faq_id: int | None = None
    matched_question: str | None = None
    similarity_score: float | None = None
    alternative_matches: list[AlternativeMatch] = field(default_factory=list)

    @property
    def is_answered(self) -> bool:
        """True when a curated answer cleared the confidence bar."""
        return self.status is AnswerStatus.ANSWER_FOUND


class FAQService:
    """Orchestrates search + confidence handling + unanswered logging."""

    def __init__(
        self,
        conn: sqlite3.Connection,
        search: SemanticSearch | None = None,
    ) -> None:
        self._conn = conn
        self._search = search or SemanticSearch()

    def answer_question(self, question: str, top_k: int | None = None) -> AnswerResult:
        """Run the full pipeline and return a structured answer.

        Never raises for ordinary failures (empty input, missing index, search
        errors) — those become ``ERROR``/``NO_MATCH`` results so the UI has one
        thing to render.
        """
        user_question = (question or "").strip()
        if not user_question:
            return AnswerResult(
                user_question="",
                status=AnswerStatus.ERROR,
                answer="Please enter a question.",
                confidence_level=ConfidenceLevel.NONE,
            )

        try:
            candidates = self._search.search(self._conn, user_question, top_k=top_k)
        except IndexNotBuiltError:
            logger.warning("Answer requested but no index is built.")
            return AnswerResult(
                user_question=user_question,
                status=AnswerStatus.ERROR,
                answer="The FAQ index has not been built yet. Please try again shortly.",
                confidence_level=ConfidenceLevel.NONE,
            )
        except Exception:  # pragma: no cover - defensive catch-all
            logger.exception("Unexpected error during search.")
            return AnswerResult(
                user_question=user_question,
                status=AnswerStatus.ERROR,
                answer="Something went wrong while searching. Please try again.",
                confidence_level=ConfidenceLevel.NONE,
            )

        if not candidates:
            self._log_unanswered(user_question, None)
            return AnswerResult(
                user_question=user_question,
                status=AnswerStatus.NO_MATCH,
                answer=FALLBACK_MESSAGE,
                confidence_level=ConfidenceLevel.NONE,
            )

        best = candidates[0]
        alternatives = self._to_alternatives(candidates[1:])

        if best.score >= settings.similarity_threshold_high:
            confidence = ConfidenceLevel.HIGH
        elif best.score >= settings.similarity_threshold_low:
            confidence = ConfidenceLevel.MEDIUM
        else:
            # Weak match: do not present it as authoritative.
            self._log_unanswered(user_question, best.score)
            return AnswerResult(
                user_question=user_question,
                status=AnswerStatus.LOW_CONFIDENCE,
                answer=FALLBACK_MESSAGE,
                confidence_level=ConfidenceLevel.LOW,
                matched_faq_id=best.faq_id,
                matched_question=best.question,
                similarity_score=best.score,
                alternative_matches=alternatives,
            )

        return AnswerResult(
            user_question=user_question,
            status=AnswerStatus.ANSWER_FOUND,
            answer=best.answer,
            confidence_level=confidence,
            matched_faq_id=best.faq_id,
            matched_question=best.question,
            similarity_score=best.score,
            alternative_matches=alternatives,
        )

    @staticmethod
    def _to_alternatives(candidates: list[SearchCandidate]) -> list[AlternativeMatch]:
        return [
            AlternativeMatch(faq_id=c.faq_id, question=c.question, score=c.score)
            for c in candidates
        ]

    def _log_unanswered(self, question: str, best_score: float | None) -> None:
        """Record a low-confidence / no-match question for admin review."""
        try:
            UnansweredRepository(self._conn).log(question, best_score)
        except sqlite3.Error:  # pragma: no cover - logging must never break answering
            logger.exception("Failed to log unanswered question.")
