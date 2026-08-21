"""Data-access layer (repositories) over SQLite.

Repositories are the *only* place that speaks SQL. UI and services depend on
these typed methods, never on raw cursors. Every query is parameterized — user
input is never string-interpolated into SQL.

Each repository takes an open :class:`sqlite3.Connection` (see
:mod:`app.database.connection`); the caller owns the connection's lifecycle and
transaction boundary. This keeps repositories easy to test (pass an in-memory
connection) and lets a single request group several operations in one commit.
"""

from __future__ import annotations

import json
import sqlite3
from dataclasses import dataclass, field


class DuplicateFAQError(ValueError):
    """Raised when adding an FAQ whose question already exists."""


# --------------------------------------------------------------------------- #
# Domain models
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FAQ:
    """A single curated FAQ record."""

    id: int
    question: str
    answer: str
    category: str
    tags: list[str] = field(default_factory=list)
    is_active: bool = True
    created_at: str | None = None
    updated_at: str | None = None


@dataclass(frozen=True)
class Feedback:
    """A user's helpfulness signal for a returned answer."""

    id: int
    faq_id: int | None
    user_question: str
    similarity_score: float | None
    was_helpful: bool | None
    created_at: str | None = None


@dataclass(frozen=True)
class UnansweredQuestion:
    """A question the bot could not answer confidently, logged for review."""

    id: int
    question: str
    best_similarity_score: float | None
    reviewed: bool
    created_at: str | None = None


# --------------------------------------------------------------------------- #
# Serialization helpers
# --------------------------------------------------------------------------- #
def _tags_to_db(tags: list[str] | None) -> str:
    return json.dumps(tags or [])


def _tags_from_db(raw: str | None) -> list[str]:
    if not raw:
        return []
    try:
        value = json.loads(raw)
        return [str(t) for t in value] if isinstance(value, list) else []
    except json.JSONDecodeError:
        return []


def _row_to_faq(row: sqlite3.Row) -> FAQ:
    return FAQ(
        id=row["id"],
        question=row["question"],
        answer=row["answer"],
        category=row["category"],
        tags=_tags_from_db(row["tags"]),
        is_active=bool(row["is_active"]),
        created_at=row["created_at"],
        updated_at=row["updated_at"],
    )


# --------------------------------------------------------------------------- #
# FAQ repository
# --------------------------------------------------------------------------- #
class FAQRepository:
    """CRUD and queries for the ``faqs`` table."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(
        self,
        question: str,
        answer: str,
        category: str = "General",
        tags: list[str] | None = None,
        is_active: bool = True,
    ) -> int:
        """Insert a new FAQ and return its id.

        Raises:
            DuplicateFAQError: if an FAQ with the same question already exists.
            ValueError: if question or answer is empty after stripping.
        """
        q, a = question.strip(), answer.strip()
        if not q or not a:
            raise ValueError("FAQ question and answer must both be non-empty.")
        try:
            cur = self._conn.execute(
                """
                INSERT INTO faqs (question, answer, category, tags, is_active)
                VALUES (?, ?, ?, ?, ?)
                """,
                (q, a, category.strip() or "General", _tags_to_db(tags), int(is_active)),
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateFAQError(f"An FAQ with this question already exists: {q!r}") from exc
        return int(cur.lastrowid)

    def get(self, faq_id: int) -> FAQ | None:
        """Return the FAQ with the given id, or ``None`` if absent."""
        row = self._conn.execute("SELECT * FROM faqs WHERE id = ?", (faq_id,)).fetchone()
        return _row_to_faq(row) if row else None

    def update(
        self,
        faq_id: int,
        *,
        question: str | None = None,
        answer: str | None = None,
        category: str | None = None,
        tags: list[str] | None = None,
        is_active: bool | None = None,
    ) -> bool:
        """Update the given fields on an FAQ. Returns True if a row changed.

        Only non-``None`` arguments are applied, so callers can patch a subset of
        fields. ``updated_at`` is refreshed automatically.
        """
        sets: list[str] = []
        params: list[object] = []
        if question is not None:
            sets.append("question = ?")
            params.append(question.strip())
        if answer is not None:
            sets.append("answer = ?")
            params.append(answer.strip())
        if category is not None:
            sets.append("category = ?")
            params.append(category.strip() or "General")
        if tags is not None:
            sets.append("tags = ?")
            params.append(_tags_to_db(tags))
        if is_active is not None:
            sets.append("is_active = ?")
            params.append(int(is_active))

        if not sets:
            return False
        sets.append("updated_at = CURRENT_TIMESTAMP")
        params.append(faq_id)

        try:
            cur = self._conn.execute(
                f"UPDATE faqs SET {', '.join(sets)} WHERE id = ?", params
            )
        except sqlite3.IntegrityError as exc:
            raise DuplicateFAQError("Another FAQ with this question already exists.") from exc
        return cur.rowcount > 0

    def set_active(self, faq_id: int, active: bool) -> bool:
        """Soft-delete / restore by toggling ``is_active``."""
        return self.update(faq_id, is_active=active)

    def delete(self, faq_id: int) -> bool:
        """Hard-delete an FAQ (cascades to its feedback). Returns True if removed.

        Prefer :meth:`set_active` for routine removals; hard delete is permanent.
        """
        cur = self._conn.execute("DELETE FROM faqs WHERE id = ?", (faq_id,))
        return cur.rowcount > 0

    def list_all(self, include_inactive: bool = True) -> list[FAQ]:
        """List FAQs ordered by id. Set ``include_inactive=False`` for active only."""
        sql = "SELECT * FROM faqs"
        if not include_inactive:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY id"
        return [_row_to_faq(r) for r in self._conn.execute(sql).fetchall()]

    def list_active(self) -> list[FAQ]:
        """Active FAQs, ordered by id — the exact set the FAISS index is built from."""
        rows = self._conn.execute(
            "SELECT * FROM faqs WHERE is_active = 1 ORDER BY id"
        ).fetchall()
        return [_row_to_faq(r) for r in rows]

    def search(self, term: str, include_inactive: bool = True) -> list[FAQ]:
        """Substring search over question/answer/category (admin convenience)."""
        like = f"%{term.strip()}%"
        sql = (
            "SELECT * FROM faqs "
            "WHERE (question LIKE ? OR answer LIKE ? OR category LIKE ?)"
        )
        params: list[object] = [like, like, like]
        if not include_inactive:
            sql += " AND is_active = 1"
        sql += " ORDER BY id"
        return [_row_to_faq(r) for r in self._conn.execute(sql, params).fetchall()]

    def list_categories(self) -> list[str]:
        """Distinct categories present, alphabetically."""
        rows = self._conn.execute(
            "SELECT DISTINCT category FROM faqs ORDER BY category"
        ).fetchall()
        return [r["category"] for r in rows]

    def count_active(self) -> int:
        """Number of active FAQs — used to validate index consistency (Phase 4)."""
        row = self._conn.execute("SELECT COUNT(*) AS n FROM faqs WHERE is_active = 1").fetchone()
        return int(row["n"])


# --------------------------------------------------------------------------- #
# Feedback repository
# --------------------------------------------------------------------------- #
class FeedbackRepository:
    """Insert and read user feedback."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def add(
        self,
        user_question: str,
        faq_id: int | None,
        similarity_score: float | None,
        was_helpful: bool | None,
    ) -> int:
        """Record one feedback row and return its id."""
        cur = self._conn.execute(
            """
            INSERT INTO feedback (faq_id, user_question, similarity_score, was_helpful)
            VALUES (?, ?, ?, ?)
            """,
            (
                faq_id,
                user_question.strip(),
                similarity_score,
                None if was_helpful is None else int(was_helpful),
            ),
        )
        return int(cur.lastrowid)

    def list_recent(self, limit: int = 100) -> list[Feedback]:
        """Most recent feedback first."""
        rows = self._conn.execute(
            "SELECT * FROM feedback ORDER BY id DESC LIMIT ?", (limit,)
        ).fetchall()
        return [
            Feedback(
                id=r["id"],
                faq_id=r["faq_id"],
                user_question=r["user_question"],
                similarity_score=r["similarity_score"],
                was_helpful=None if r["was_helpful"] is None else bool(r["was_helpful"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]


# --------------------------------------------------------------------------- #
# Unanswered-question repository
# --------------------------------------------------------------------------- #
class UnansweredRepository:
    """Log and review questions the bot could not answer confidently."""

    def __init__(self, conn: sqlite3.Connection) -> None:
        self._conn = conn

    def log(self, question: str, best_similarity_score: float | None) -> int:
        """Record a low-confidence/no-match question and return its id."""
        cur = self._conn.execute(
            """
            INSERT INTO unanswered_questions (question, best_similarity_score)
            VALUES (?, ?)
            """,
            (question.strip(), best_similarity_score),
        )
        return int(cur.lastrowid)

    def list(self, only_unreviewed: bool = False, limit: int = 200) -> list[UnansweredQuestion]:
        """List logged questions, most recent first."""
        sql = "SELECT * FROM unanswered_questions"
        if only_unreviewed:
            sql += " WHERE reviewed = 0"
        sql += " ORDER BY id DESC LIMIT ?"
        rows = self._conn.execute(sql, (limit,)).fetchall()
        return [
            UnansweredQuestion(
                id=r["id"],
                question=r["question"],
                best_similarity_score=r["best_similarity_score"],
                reviewed=bool(r["reviewed"]),
                created_at=r["created_at"],
            )
            for r in rows
        ]

    def mark_reviewed(self, unanswered_id: int, reviewed: bool = True) -> bool:
        """Flag a logged question as reviewed (or not). Returns True if changed."""
        cur = self._conn.execute(
            "UPDATE unanswered_questions SET reviewed = ? WHERE id = ?",
            (int(reviewed), unanswered_id),
        )
        return cur.rowcount > 0
