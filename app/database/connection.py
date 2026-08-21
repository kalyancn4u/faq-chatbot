"""SQLite connection management.

One small module that every data-access path goes through, so connection
concerns (foreign-key enforcement, row access by name, transaction boundaries)
are configured in exactly one place.

Design notes:
- SQLite does **not** enforce foreign keys unless ``PRAGMA foreign_keys = ON`` is
  issued per connection, so we do it on every connect.
- ``row_factory = sqlite3.Row`` lets callers read columns by name (``row["id"]``)
  instead of by fragile positional index.
- :func:`get_connection` is a context manager that commits on success, rolls back
  on any exception, and always closes — the safe default for a unit of work.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator
from contextlib import contextmanager
from pathlib import Path

from app.config.settings import settings


def connect(db_path: Path | str | None = None) -> sqlite3.Connection:
    """Open a configured SQLite connection.

    Args:
        db_path: Database file path. Defaults to the configured ``DB_PATH``.
            Pass ``":memory:"`` for an ephemeral in-memory database (useful in
            tests). The parent directory is created for file-based databases.

    Returns:
        An open connection with foreign keys enabled and row-name access.
    """
    target = db_path if db_path is not None else settings.db_path
    if target != ":memory:":
        Path(target).parent.mkdir(parents=True, exist_ok=True)

    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


@contextmanager
def get_connection(db_path: Path | str | None = None) -> Iterator[sqlite3.Connection]:
    """Context manager yielding a connection as a single unit of work.

    Commits if the ``with`` block succeeds, rolls back if it raises, and always
    closes the connection.

    Example::

        with get_connection() as conn:
            FAQRepository(conn).add(...)
    """
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()
