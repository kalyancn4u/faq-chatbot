"""CLI to import FAQs from a CSV file into SQLite.

The importable logic lives in :mod:`app.database.csv_import` (shared by the admin
UI); this script is just the command-line wrapper.

CLI::

    python scripts/import_faqs.py data/sample/faqs.csv
"""

from __future__ import annotations

import _bootstrap  # noqa: F401  (adds project root to sys.path)

import argparse

from app.config.logging_config import get_logger
from app.database.connection import get_connection
from app.database.csv_import import import_faqs_from_csv

logger = get_logger(__name__)


def main() -> None:
    parser = argparse.ArgumentParser(description="Import FAQs from a CSV file.")
    parser.add_argument(
        "csv_path",
        nargs="?",
        default="data/sample/faqs.csv",
        help="Path to the CSV file (default: data/sample/faqs.csv).",
    )
    args = parser.parse_args()

    with get_connection() as conn:
        result = import_faqs_from_csv(conn, args.csv_path)

    logger.info(
        "Import complete: %d inserted, %d duplicates skipped, %d invalid skipped.",
        result.inserted,
        result.skipped_duplicate,
        result.skipped_invalid,
    )
    for err in result.errors:
        logger.warning(err)


if __name__ == "__main__":
    main()
