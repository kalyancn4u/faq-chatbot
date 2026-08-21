"""Admin service — FAQ management, CSV import/export, and index operations.

Groups the operations the admin UI needs behind one class so the UI stays thin.
It composes existing pieces rather than reimplementing them: FAQ CRUD comes from
:class:`~app.database.repository.FAQRepository`, CSV import reuses the single
importer in :mod:`scripts.import_faqs` (one code path for CLI and UI), and index
rebuild/status come from :class:`~app.retrieval.index_manager.IndexManager`.
"""

from __future__ import annotations

import csv
import io
import sqlite3

from app.database.csv_import import ImportResult, import_faqs_from_csv
from app.database.repository import FAQ, FAQRepository
from app.retrieval.index_manager import IndexManager, IndexStatus, RebuildResult


class AdminService:
    """Operations backing the admin interface."""

    def __init__(self, conn: sqlite3.Connection, index_manager: IndexManager | None = None) -> None:
        self._conn = conn
        self._repo = FAQRepository(conn)
        self._index = index_manager or IndexManager()

    # --- FAQ CRUD ---------------------------------------------------------- #
    def add_faq(
        self, question: str, answer: str, category: str = "General", tags: list[str] | None = None
    ) -> int:
        return self._repo.add(question, answer, category=category, tags=tags)

    def update_faq(self, faq_id: int, **fields) -> bool:
        return self._repo.update(faq_id, **fields)

    def set_active(self, faq_id: int, active: bool) -> bool:
        return self._repo.set_active(faq_id, active)

    def delete_faq(self, faq_id: int) -> bool:
        return self._repo.delete(faq_id)

    def get_faq(self, faq_id: int) -> FAQ | None:
        return self._repo.get(faq_id)

    def list_faqs(self, include_inactive: bool = True) -> list[FAQ]:
        return self._repo.list_all(include_inactive=include_inactive)

    def search_faqs(self, term: str) -> list[FAQ]:
        return self._repo.search(term)

    def list_categories(self) -> list[str]:
        return self._repo.list_categories()

    # --- CSV import / export ---------------------------------------------- #
    def import_csv(self, csv_path: str) -> ImportResult:
        """Validate and import FAQs from a CSV file path."""
        return import_faqs_from_csv(self._conn, csv_path)

    def export_csv(self) -> str:
        """Serialize all FAQs to CSV text (pipe-separated tags)."""
        buffer = io.StringIO()
        writer = csv.writer(buffer)
        writer.writerow(["question", "answer", "category", "tags", "is_active"])
        for faq in self._repo.list_all(include_inactive=True):
            writer.writerow(
                [faq.question, faq.answer, faq.category, "|".join(faq.tags), int(faq.is_active)]
            )
        return buffer.getvalue()

    # --- Index operations -------------------------------------------------- #
    def rebuild_index(self) -> RebuildResult:
        return self._index.rebuild(self._conn)

    def index_status(self) -> IndexStatus:
        return self._index.status(self._conn)
