# Chapter 3 — The Database Layer

*SQLite as the system of record, and the patterns that keep data access safe.*

**By the end of this chapter you will be able to:** explain why SQLite is the
source of truth, read the schema, use the repository pattern, understand
parameterized queries and soft-delete, and follow the CSV import.

Files: [`connection.py`](../../app/database/connection.py),
[`schema.py`](../../app/database/schema.py),
[`repository.py`](../../app/database/repository.py),
[`csv_import.py`](../../app/database/csv_import.py).

---

## Why SQLite?

***SQLite*** is a full SQL database that lives in a **single file** with **no
server** to install or run.[1] For a local-first app it is close to ideal:

- zero setup — just a `.db` file on disk,
- transactional and reliable,
- perfect as the **authoritative** store for FAQs, feedback, and logs.

Recall Design Law #1: this is the truth; FAISS is rebuilt from it.[2]

> **Footnotes**
> [1] Contrast with client-server databases (PostgreSQL, MySQL) that need a running
> service. SQLite is embedded *in* your process. It's the most deployed database in
> the world — it's in your phone and browser. See sqlite.org.
> [2] Keeping *structured, authoritative* data in SQL and *semantic search* in FAISS
> is a clean division of labor: each tool does what it's best at.

---

## The connection: one safe door in and out

Every database access goes through one small module so connection concerns are
configured in exactly one place:

```python
# app/database/connection.py
def connect(db_path=None) -> sqlite3.Connection:
    conn = sqlite3.connect(target)
    conn.row_factory = sqlite3.Row               # access columns by name
    conn.execute("PRAGMA foreign_keys = ON;")    # enforce relationships
    return conn
```

Two easy-to-miss but crucial lines:

- `row_factory = sqlite3.Row` lets you write `row["question"]` instead of a fragile
  `row[1]`.[1]
- `PRAGMA foreign_keys = ON` — SQLite does **not** enforce foreign keys by default;
  you must switch it on *per connection*.[2]

> **Footnotes**
> [1] Positional access (`row[1]`) silently breaks the moment a column is added or
> reordered. Name access is self-documenting and robust.
> [2] A ***foreign key*** links a row in one table to a row in another (e.g. feedback
> → the FAQ it's about). "Enforce" means the database rejects orphaned links. It's
> off by default in SQLite for historical compatibility — a classic gotcha.

---

## The unit-of-work context manager

```python
# app/database/connection.py
@contextmanager
def get_connection(db_path=None):
    conn = connect(db_path)
    try:
        yield conn
        conn.commit()        # success → save everything
    except Exception:
        conn.rollback()      # failure → undo everything
        raise
    finally:
        conn.close()         # always release the file
```

Used as:

```python
# any caller — pattern from app/database/connection.py
with get_connection() as conn:
    FAQRepository(conn).add(...)     # commits automatically if no error
```

This guarantees a **transaction**[1]: either all the writes in the block succeed
together, or none do. You cannot forget to commit or leak a connection.

> **Footnotes**
> [1] A ***transaction*** is an all-or-nothing unit of work. If the block raises
> halfway, `rollback()` restores the database to its pre-block state — no
> half-written data. `finally` runs no matter what, so the file is always closed.

---

## The schema: tables, keys, constraints

```sql
-- app/database/schema.py
CREATE TABLE IF NOT EXISTS faqs (
    id         INTEGER PRIMARY KEY AUTOINCREMENT,
    question   TEXT NOT NULL UNIQUE,
    answer     TEXT NOT NULL,
    category   TEXT NOT NULL DEFAULT 'General',
    tags       TEXT NOT NULL DEFAULT '[]',   -- JSON array
    is_active  INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0,1)),
    created_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP),
    updated_at TEXT NOT NULL DEFAULT (CURRENT_TIMESTAMP)
);
```

Design decisions worth noticing:

- `question ... UNIQUE` — exact-duplicate questions are rejected by the database
  itself.[1]
- `is_active` with a `CHECK` — enables **soft-delete** (Chapter slide ahead) and
  guarantees the value is only 0 or 1.[2]
- `tags` stored as a JSON string — simple and transparent; no extra table needed.[3]

The `feedback` and `unanswered_questions` tables follow the same care, including a
foreign key with `ON DELETE CASCADE`.[4]

> **Footnotes**
> [1] Semantic paraphrases ("I forgot my password") are *different* rows on purpose —
> each becomes its own searchable anchor (Chapter 5). Only *identical* text is
> blocked.
> [2] A ***constraint*** is a rule the database enforces on every write. `CHECK`
> rejects invalid values before they can corrupt your data.
> [3] `["password","login"]` is stored as text and parsed back to a Python list by
> the repository. A separate tags table would be premature for V1.
> [4] `ON DELETE CASCADE` means "if an FAQ is hard-deleted, delete its feedback
> too," so no orphaned rows remain. The schema is `IF NOT EXISTS`, i.e.
> ***idempotent*** — safe to run on every startup.

---

## The repository pattern: the only place SQL lives

All SQL is confined to *repository* classes; the rest of the app calls typed
methods, never raw cursors.[1]

```python
# app/database/repository.py
class FAQRepository:
    def __init__(self, conn): self._conn = conn

    def add(self, question, answer, category="General", tags=None, is_active=True):
        ...
        cur = self._conn.execute(
            "INSERT INTO faqs (question, answer, category, tags, is_active) "
            "VALUES (?, ?, ?, ?, ?)",
            (q, a, category, _tags_to_db(tags), int(is_active)),
        )
        return int(cur.lastrowid)
```

Benefits:

- SQL changes happen in **one** file, not scattered across the UI.[2]
- Methods return **typed dataclasses** (`FAQ`, `Feedback`, …), so callers work with
  objects, not tuples.
- The repository takes a connection, so the **caller owns the transaction** — one
  request can group several writes into one commit.[3]

> **Footnotes**
> [1] The ***repository pattern*** puts all persistence logic behind a small, typed
> interface. Swap SQLite for something else later and only repositories change.
> [2] Compare to SQL strings sprinkled through button handlers — impossible to audit
> for correctness or security.
> [3] This design also makes tests trivial: pass an in-memory connection and the
> repository works unchanged (Chapter 9).

---

## Parameterized queries (never build SQL by hand)

Notice the `?` placeholders above. The values are passed **separately** from the
SQL text:

```python
# app/database/repository.py — the safe pattern used everywhere
self._conn.execute("... WHERE id = ?", (faq_id,))   # ✅ safe
```

Never do this (anti-example — appears nowhere in the codebase):

```python
# ❌ anti-pattern — NOT in this project
self._conn.execute(f"... WHERE id = {faq_id}")      # ❌ SQL injection risk
```

With placeholders, user input can never be interpreted as SQL commands — the driver
treats it strictly as data.[1]

⚠️ **Pitfall:** f-string SQL is the #1 database security hole. A question like
`'; DROP TABLE faqs;--` becomes a catastrophe with string-building, and a harmless
literal with placeholders.

> **Footnotes**
> [1] ***SQL injection*** is when attacker-supplied text is executed as SQL.
> ***Parameterized queries*** (a.k.a. prepared statements) separate code from data so
> injection is impossible by construction. This is non-negotiable in real software.

---

## Soft-delete: remove without losing history

```python
# app/database/repository.py
def set_active(self, faq_id, active):        # the default "delete"
    return self.update(faq_id, is_active=active)

def delete(self, faq_id):                    # permanent; used rarely
    ...
```

The app prefers **deactivating** (`is_active = 0`) over hard deletion:

- inactive FAQs are excluded from the FAISS index and from answers,
- but their rows (and any feedback) remain for history and auditing.[1]

Only `is_active = 1` rows are indexed — this is the exact set FAISS is built from
(Chapter 5).

> **Footnotes**
> [1] ***Soft-delete*** = mark as removed instead of erasing. It's reversible,
> preserves referential history, and prevents "why did this feedback vanish?"
> surprises. Hard delete stays available for genuine purges.

---

## CSV import: validate *before* you write

The importer checks every row before touching the database, and reports outcomes:

```python
# app/database/csv_import.py
def import_faqs_from_csv(conn, csv_path) -> ImportResult:
    # required columns present? else raise a clear error
    # per row: non-empty question & answer? unique? then insert, else count as skipped
```

- Duplicates (in the file or already in the DB) are **skipped and counted**, not
  fatal.[1]
- One shared importer serves both the CLI script and the admin UI — a single code
  path, no duplication.[2]

🛠️ **Try it:** run `python scripts/import_faqs.py data/sample/faqs.csv` twice. The
second run reports 30 duplicates skipped — proof the guard works.

> **Footnotes**
> [1] Returning a structured `ImportResult` (inserted / skipped_duplicate /
> skipped_invalid / errors) lets callers show a friendly summary instead of a stack
> trace. Robustness for messy real-world CSVs.
> [2] The logic lives in `app/database/csv_import.py`; the script and the admin
> service both import it. "One source of truth" applies to *behavior*, not just
> config.

---

## Recap & what's next

- SQLite is the **authoritative** single-file store.
- **Connection** is centralized; the **context manager** gives all-or-nothing
  transactions.
- The **schema** uses keys, constraints, and cascades; the **repository** confines
  all SQL and uses **parameterized queries**.
- **Soft-delete** preserves history; **CSV import** validates first.

**Next:** [Chapter 4 — Embeddings](04-embeddings.md): the moment text becomes
numbers, and why that lets us search by meaning.
