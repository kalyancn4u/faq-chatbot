# Glossary

Plain-language definitions of every term used in the walk-through. Skim it once, then
use it as a lookup. Each entry notes the chapter where the idea is used.

---

### Atomic
An operation that either completes fully or not at all, with no visible half-done
state. The index rebuild replaces files atomically with `os.replace`. *(Ch 5)*

### Confidence band
One of three tiers — **High / Medium / Low** — decided by comparing a match's cosine
score to two thresholds. Determines whether the user gets the answer, a caveated
answer, or a fallback. *(Ch 6)*

### Constraint (database)
A rule the database enforces on every write, e.g. `UNIQUE`, `CHECK`, or a foreign
key. Rejects invalid data before it can be stored. *(Ch 3)*

### Context manager
A Python `with`-block helper that guarantees setup and cleanup. `get_connection()`
uses one to commit on success, roll back on error, and always close. *(Ch 3)*

### Cosine similarity
A measure of how aligned two vectors' directions are: 1 = same meaning, 0 =
unrelated. For unit-length vectors it equals the dot product. *(Ch 4)*

### Dataclass
A Python class whose fields are declared by name and type; the `@dataclass`
decorator writes the boilerplate. `frozen=True` makes instances immutable. *(Ch 2)*

### Derived artifact
Something computed from a source of truth and safe to regenerate — like a compiled
binary from source. The FAISS index is derived from SQLite. *(Ch 1, 5)*

### Embedding
A fixed-length list of numbers (a vector) representing the *meaning* of text.
Similar meanings → nearby vectors. *(Ch 4)*

### Embedding space
The multi-dimensional number space embeddings live in; directions correspond roughly
to aspects of meaning. *(Ch 4)*

### Enum
A type with a fixed set of named values (e.g. `AnswerStatus.ANSWER_FOUND`). Makes
valid states explicit and typo-proof. *(Ch 6)*

### FAISS
Facebook AI Similarity Search — a library for fast nearest-vector search. We use the
CPU build and an exact `IndexFlatIP`. *(Ch 5)*

### Fail fast / fail loud
Detect an invalid state at the earliest, clearest point and stop, rather than
continuing into a confusing crash later. *(Ch 2, 5)*

### Fixture (pytest)
Reusable test setup that pytest injects by name and tears down afterward. Our
`conn`/`seeded_conn`/`embedder` fixtures isolate each test. *(Ch 9)*

### Foreign key
A column linking a row to a row in another table (e.g. feedback → its FAQ). SQLite
enforces them only when `PRAGMA foreign_keys = ON`. *(Ch 3)*

### Hydrate
Fill a bare reference with full data — here, turning a `faq_id` from FAISS into the
complete FAQ record from SQLite. *(Ch 6)*

### Idempotent
Safe to run repeatedly with the same effect as running once. The schema DDL
(`CREATE TABLE IF NOT EXISTS`) and logging setup are idempotent. *(Ch 2, 3)*

### IndexFlatIP
A FAISS index that stores vectors plainly and scans them all (exact) using inner
product ("IP"). With normalized vectors, IP = cosine. *(Ch 5)*

### Invariant
A condition that must always hold. The consistency invariant:
`indexed vectors == mapped ids == active FAQs`. *(Ch 5)*

### Lazy import / lazy loading
Importing or loading something only when first needed, not up front — keeps startup
and unrelated tools fast. The embedder imports PyTorch lazily. *(Ch 4)*

### L2 normalization
Scaling a vector to length 1 so only its direction remains. Makes inner product equal
cosine similarity. *(Ch 4)*

### `lru_cache`
A decorator that memoizes a function: same arguments → cached result. Used to load
each embedding model only once. *(Ch 4)*

### MarkdownV2
Telegram's strict markdown dialect. Reserved punctuation (`. - ( ) ! >` …) must be
backslash-escaped in literal text or the send is rejected. *(Ch 7)*

### Magic number
An unexplained literal constant buried in code. The project avoids them by naming all
tunables in one config module. *(Ch 2)*

### Parameterized query
SQL with `?` placeholders whose values are passed separately, so user input can never
be executed as SQL. The defense against SQL injection. *(Ch 3)*

### Property (Python)
A method that behaves like an attribute (`settings.index_path`). Lets derived values
stay in sync with their source. *(Ch 2)*

### Pure function
A function whose output depends only on its inputs and which changes nothing else.
Easy to test and cache; `format_reply` and the HTML builders are pure. *(Ch 7, 9)*

### RAG (Retrieval-Augmented Generation)
Retrieve relevant text, then let an LLM write an answer grounded in it. A possible
future version; not in V1. *(Ch 1, 10)*

### Repository pattern
Confining all database access behind small, typed classes so SQL lives in one place
and the rest of the app works with objects. *(Ch 3)*

### Rerun (Streamlit)
Streamlit re-executes the whole script top to bottom on every interaction. Hence
`session_state` (to remember) and `cache_resource` (to avoid re-doing work). *(Ch 8)*

### Segment (SMS)
The 160-character unit SMS is billed in (153 chars each when a message spans multiple
segments). *(Ch 7)*

### `session_state`
A per-browser-session dict Streamlit keeps across reruns. Stores the chat history
(as raw results). *(Ch 8)*

### Service layer
Where business decisions live (e.g. confidence handling), separate from the UI and
the database. The UI calls `answer_question`; the service decides. *(Ch 6)*

### Side effect
Anything a piece of code does beyond returning a value (writing files, network). The
project keeps imports side-effect-free and makes such actions explicit. *(Ch 2)*

### Soft-delete
Marking a row inactive (`is_active = 0`) instead of erasing it — reversible and
history-preserving. The default way to "remove" an FAQ. *(Ch 3)*

### SQL injection
An attack where user text is executed as SQL. Prevented entirely by parameterized
queries. *(Ch 3)*

### SQLite
A full SQL database in a single file with no server. The app's system of record.
*(Ch 3)*

### Staleness
The index being out of date — missing, built with a different model, or not matching
the current active-FAQ set. Triggers a rebuild. *(Ch 5)*

### System of record
The authoritative copy of data; if stores disagree, this one wins. Here, SQLite.
*(Ch 1, 3)*

### Threshold (similarity)
A cutoff score that separates confidence bands. `SIMILARITY_THRESHOLD_HIGH/LOW`,
tuned empirically — never treated as universally correct. *(Ch 2, 6)*

### Top-k
The number of nearest candidates a search returns (`TOP_K`, default 5). *(Ch 5, 6)*

### Transaction
An all-or-nothing unit of database work: commit on success, roll back on failure.
*(Ch 3)*

### Twelve-factor app
A set of practices for building software; the relevant one here is "store config in
the environment," separate from code. *(Ch 2)*

### Vector
A fixed-length array of numbers. An embedding is a vector; FAISS searches over
vectors. *(Ch 4, 5)*

### Vector index
A data structure that finds the nearest stored vectors to a query vector quickly.
FAISS provides ours. *(Ch 1, 5)*

---

*Back to the [walk-through index](README.md).*
