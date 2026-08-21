"""Rebuild the FAISS index from the active FAQs in SQLite.

Run this whenever FAQs change (add / edit / activate / deactivate). It performs a
full rebuild, validates consistency, and atomically replaces the old index.

CLI::

    python scripts/rebuild_index.py            # rebuild
    python scripts/rebuild_index.py --status   # show index/DB status only
"""

from __future__ import annotations

import _bootstrap  # noqa: F401  (adds project root to sys.path)

import argparse

from app.config.logging_config import get_logger
from app.config.settings import ensure_directories
from app.database.connection import get_connection
from app.retrieval.index_manager import IndexManager

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Rebuild or inspect the FAISS index.")
    parser.add_argument("--status", action="store_true", help="Show status without rebuilding.")
    args = parser.parse_args()

    ensure_directories()
    manager = IndexManager()

    with get_connection() as conn:
        if args.status:
            s = manager.status(conn)
            logger.info(
                "Index status: exists=%s stale=%s vectors=%d mapped=%d active_faqs=%d model=%s dim=%s",
                s.exists, s.is_stale, s.indexed_vectors, s.mapped_ids,
                s.active_faqs, s.model_name, s.dimension,
            )
            return

        result = manager.rebuild(conn)
        logger.info(
            "Rebuild complete: %d FAQs indexed (model=%s, dim=%d).",
            result.faq_count, result.model_name, result.dimension,
        )


if __name__ == "__main__":
    main()
