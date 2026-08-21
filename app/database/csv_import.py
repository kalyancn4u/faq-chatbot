"""Reusable CSV → SQLite FAQ import (one code path for CLI and the admin UI).

CSV format (header required)::

    question,answer,category,tags

- ``question`` and ``answer`` are required and must be non-empty.
- ``category`` is optional (defaults to ``General``).
- ``tags`` is optional: a pipe-separated list, e.g. ``password|login|reset``.

Rows are **validated before writing**, and duplicate questions (already present,
or repeated within the file) are skipped and reported rather than aborting.
"""

from __future__ import annotations

import csv
import sqlite3
from dataclasses import dataclass, field
from pathlib import Path

from app.database.repository import DuplicateFAQError, FAQRepository

REQUIRED_COLUMNS = {"question", "answer"}


@dataclass
class ImportResult:
    """Summary of a CSV import run."""

    inserted: int = 0
    skipped_duplicate: int = 0
    skipped_invalid: int = 0
    errors: list[str] = field(default_factory=list)

    @property
    def total_processed(self) -> int:
        return self.inserted + self.skipped_duplicate + self.skipped_invalid


def _parse_tags(raw: str | None) -> list[str]:
    if not raw:
        return []
    return [t.strip() for t in raw.split("|") if t.strip()]


def import_faqs_from_csv(conn: sqlite3.Connection, csv_path: Path | str) -> ImportResult:
    """Validate and import FAQs from ``csv_path`` using an open connection.

    The caller owns the transaction; commit the connection to persist on success.

    Raises:
        FileNotFoundError: if the CSV does not exist.
        ValueError: if required columns are missing.
    """
    path = Path(csv_path)
    if not path.is_file():
        raise FileNotFoundError(f"CSV file not found: {path}")

    repo = FAQRepository(conn)
    result = ImportResult()
    seen_questions: set[str] = set()

    with path.open(newline="", encoding="utf-8") as fh:
        reader = csv.DictReader(fh)
        header = {c.strip().lower() for c in (reader.fieldnames or [])}
        missing = REQUIRED_COLUMNS - header
        if missing:
            raise ValueError(
                f"CSV is missing required column(s): {', '.join(sorted(missing))}"
            )

        for line_no, row in enumerate(reader, start=2):  # row 1 is the header
            question = (row.get("question") or "").strip()
            answer = (row.get("answer") or "").strip()
            category = (row.get("category") or "General").strip() or "General"
            tags = _parse_tags(row.get("tags"))

            if not question or not answer:
                result.skipped_invalid += 1
                result.errors.append(f"Line {line_no}: missing question or answer.")
                continue

            key = question.lower()
            if key in seen_questions:
                result.skipped_duplicate += 1
                continue
            seen_questions.add(key)

            try:
                repo.add(question, answer, category=category, tags=tags)
                result.inserted += 1
            except DuplicateFAQError:
                result.skipped_duplicate += 1
            except ValueError as exc:
                result.skipped_invalid += 1
                result.errors.append(f"Line {line_no}: {exc}")

    return result
