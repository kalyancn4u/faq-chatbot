"""Database schema definition and initialization.

The SQLite database is the **authoritative system of record** for FAQs, user
feedback, and logged unanswered questions. The FAISS index (Phase 4) is derived
from the ``faqs`` table and can always be rebuilt from it.

All DDL is idempotent (``IF NOT EXISTS``) so :func:`initialize_database` is safe
to run repeatedly.
"""

from __future__ import annotations

import sqlite3

# --- faqs: the curated knowledge base (source of truth) ---
# `question` is UNIQUE so exact-duplicate questions are rejected at the DB level;
# semantic paraphrases are intentionally separate rows (each becomes its own
# searchable anchor). `is_active` enables soft-delete: inactive rows are excluded
# from the FAISS index but kept for history/feedback integrity.
_CREATE_FAQS = """
CREATE TABLE IF NOT EXISTS faqs (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    question    TEXT    NOT NULL UNIQUE,
    answer      TEXT    NOT NULL,
    category    TEXT    NOT NULL DEFAULT 'General',
    tags        TEXT    NOT NULL DEFAULT '[]',   -- JSON array of strings
    is_active   INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    created_at  TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at  TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);
"""

# --- feedback: was a returned answer helpful? Drives coverage/threshold tuning ---
# ON DELETE CASCADE: if an FAQ is ever hard-deleted, its feedback goes with it.
_CREATE_FEEDBACK = """
CREATE TABLE IF NOT EXISTS feedback (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    faq_id            INTEGER,
    user_question     TEXT    NOT NULL,
    similarity_score  REAL,
    was_helpful       INTEGER CHECK (was_helpful IN (0, 1)),
    created_at        TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    FOREIGN KEY (faq_id) REFERENCES faqs (id) ON DELETE CASCADE
);
"""

# --- unanswered_questions: low-confidence / no-match questions, for admin review ---
_CREATE_UNANSWERED = """
CREATE TABLE IF NOT EXISTS unanswered_questions (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    question              TEXT    NOT NULL,
    best_similarity_score REAL,
    created_at            TEXT    NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    reviewed              INTEGER NOT NULL DEFAULT 0 CHECK (reviewed IN (0, 1))
);
"""

# Indexes that speed up the app's common read patterns.
_CREATE_INDEXES = [
    "CREATE INDEX IF NOT EXISTS idx_faqs_active   ON faqs (is_active);",
    "CREATE INDEX IF NOT EXISTS idx_faqs_category ON faqs (category);",
    "CREATE INDEX IF NOT EXISTS idx_feedback_faq  ON feedback (faq_id);",
    "CREATE INDEX IF NOT EXISTS idx_unanswered_reviewed ON unanswered_questions (reviewed);",
]

_ALL_STATEMENTS = [_CREATE_FAQS, _CREATE_FEEDBACK, _CREATE_UNANSWERED, *_CREATE_INDEXES]

# Table names used by consistency/status checks elsewhere.
TABLES = ("faqs", "feedback", "unanswered_questions")


def initialize_database(conn: sqlite3.Connection) -> None:
    """Create all tables and indexes if they do not already exist.

    Idempotent: safe to call on every startup.
    """
    for statement in _ALL_STATEMENTS:
        conn.execute(statement)
