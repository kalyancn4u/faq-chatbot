"""Initialize the SQLite database (create tables/indexes).

Idempotent — safe to run repeatedly. Optionally seed with the sample FAQs.

CLI::

    python scripts/initialize_database.py                 # create schema only
    python scripts/initialize_database.py --with-sample   # also import sample FAQs
"""

from __future__ import annotations

import _bootstrap  # noqa: F401  (adds project root to sys.path)

import argparse

from app.config.logging_config import get_logger
from app.config.settings import ensure_directories, settings
from app.database.connection import get_connection
from app.database.csv_import import import_faqs_from_csv
from app.database.repository import FAQRepository
from app.database.schema import initialize_database

logger = get_logger(__name__)

SAMPLE_CSV = settings.db_path.parent.parent / "sample" / "faqs.csv"


def main() -> None:
    parser = argparse.ArgumentParser(description="Initialize the FAQ database.")
    parser.add_argument(
        "--with-sample",
        action="store_true",
        help="Also import the bundled sample FAQs (data/sample/faqs.csv).",
    )
    args = parser.parse_args()

    ensure_directories()
    with get_connection() as conn:
        initialize_database(conn)
        logger.info("Schema ready at %s", settings.db_path)

        if args.with_sample:
            existing = FAQRepository(conn).count_active()
            if existing:
                logger.info("Skipping sample import: %d FAQs already present.", existing)
            else:
                result = import_faqs_from_csv(conn, SAMPLE_CSV)
                logger.info(
                    "Sample import: %d inserted, %d duplicates, %d invalid.",
                    result.inserted,
                    result.skipped_duplicate,
                    result.skipped_invalid,
                )

        total = FAQRepository(conn).count_active()
    logger.info("Done. Active FAQs in database: %d", total)


if __name__ == "__main__":
    main()
