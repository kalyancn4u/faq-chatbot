"""Shared pytest fixtures.

Design choices that keep the suite fast and hermetic:

- Each test gets its own **temp-file** SQLite database (not the project one), with
  the schema created and a small, known set of FAQs seeded.
- The real embedding model is loaded **once per session** (it is the slow part)
  and shared, so semantic tests exercise the true model without paying the load
  cost repeatedly.
- FAISS artifacts are written under pytest's ``tmp_path`` so nothing touches the
  real ``data/indexes`` directory.
"""

from __future__ import annotations

import sqlite3
from collections.abc import Iterator

import pytest

from app.database.connection import connect
from app.database.repository import FAQRepository
from app.database.schema import initialize_database
from app.embeddings.embedder import Embedder
from app.retrieval.index_manager import IndexManager

# A compact, deliberately varied FAQ set (question, answer, category).
SEED_FAQS = [
    ("How do I reset my password?", "Use the Forgot Password link on the login page.", "Account"),
    ("I forgot my password.", "Request a reset from the login page.", "Account"),
    ("How do I update my email address?", "Edit it under Settings > Profile.", "Account"),
    ("What payment methods do you accept?", "Cards and PayPal.", "Billing"),
    ("How long does shipping take?", "3-5 business days.", "Shipping"),
    ("How do I contact customer support?", "Use the Help > Contact Us form.", "General"),
]


@pytest.fixture(scope="session")
def embedder() -> Embedder:
    """Real embedding model, loaded once for the whole test session."""
    return Embedder()


@pytest.fixture
def conn(tmp_path) -> Iterator[sqlite3.Connection]:
    """A fresh, schema-initialized SQLite connection on a temp file."""
    db_file = tmp_path / "test.db"
    connection = connect(db_file)
    initialize_database(connection)
    yield connection
    connection.close()


@pytest.fixture
def seeded_conn(conn: sqlite3.Connection) -> sqlite3.Connection:
    """Connection pre-loaded with :data:`SEED_FAQS`."""
    repo = FAQRepository(conn)
    for question, answer, category in SEED_FAQS:
        repo.add(question, answer, category=category)
    conn.commit()
    return conn


@pytest.fixture
def index_manager(tmp_path, embedder: Embedder) -> IndexManager:
    """IndexManager writing to temp artifacts, using the shared embedder."""
    return IndexManager(
        embedder=embedder,
        index_path=tmp_path / "faq.faiss",
        id_map_path=tmp_path / "id_map.json",
    )


@pytest.fixture
def built_index(index_manager: IndexManager, seeded_conn: sqlite3.Connection) -> IndexManager:
    """An IndexManager with a freshly built index over the seeded FAQs."""
    index_manager.rebuild(seeded_conn)
    return index_manager
