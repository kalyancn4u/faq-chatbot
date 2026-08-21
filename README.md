# Semantic FAQ Chatbot

A local-first FAQ chatbot that understands the **meaning** of a question, not just its
keywords. Runs entirely on a normal laptop CPU — no GPU, no cloud database, no paid API,
no LLM. It retrieves **curated** answers and never fabricates them.

> "How do I reset my password?", "I forgot my password.", and "I can't remember my login
> credentials." all find the same password FAQ.

---

## Architecture

```text
User
  │
  ▼
Streamlit UI
  │
  ▼
Sentence Transformer ──► query embedding (normalized)
  │
  ▼
FAISS ───────────────► find semantically similar FAQs (top-k)
  │
  ▼
SQLite ──────────────► retrieve authoritative answer + metadata
  │
  ▼
Confidence handling ─► answer · answer-with-caveat · fallback
```

**SQLite is the system of record. FAISS is a derived semantic index.** Every FAISS vector
maps back to a SQLite FAQ id, and the two are kept consistent by an explicit rebuild +
validation step.

---

## Why SQLite + FAISS?

- **What is an embedding?** An embedding model reads a piece of text and outputs a
  fixed-length list of numbers (a *vector*) that encodes its meaning. Texts with similar
  meaning get vectors that point in nearly the same direction — which is why "I forgot my
  password" and "how do I reset my password?" end up close together even though they share
  few words. We use the `all-MiniLM-L6-v2` model (384 numbers per text), which is small and
  runs comfortably on a CPU.
- **Why FAISS?** Once every FAQ question is an embedding, answering a new question means
  "find the stored vectors closest to this one." FAISS (Facebook AI Similarity Search) does
  exactly that, very efficiently. We use an exact `IndexFlatIP` index: because vectors are
  normalized, the inner product it computes equals **cosine similarity**, and "exact" means
  no approximation to tune — ideal for a small-to-medium FAQ set.
- **Why SQLite?** FAISS only knows about vectors and their positions — it doesn't store the
  actual questions, answers, categories, feedback, or logs. SQLite holds all of that as the
  **authoritative record**, in a single file, with no server to run.
- **Why are both needed?** They do different jobs:
  `SQLite → authoritative structured data` · `FAISS → fast semantic similarity`.
  A search finds the nearest vector *positions* in FAISS, and we map those back to FAQ ids to
  fetch the real answers from SQLite. The index is derived and can always be rebuilt from the
  database.
- **Why not Chroma initially?** Chroma bundles storage + vector search and shines for larger
  RAG/document systems. For a focused FAQ app, keeping SQLite and FAISS separate is simpler
  and more transparent — you can see exactly where data lives and how consistency is
  maintained. Chroma remains an easy future swap behind the retrieval layer (see roadmap).

---

## Technology Stack

| Layer            | Choice                                   |
| ---------------- | ---------------------------------------- |
| UI               | Streamlit                                |
| Embeddings       | sentence-transformers (`all-MiniLM-L6-v2`, configurable) |
| Vector search    | FAISS (CPU)                              |
| System of record | SQLite                                   |
| Language         | Python 3.12                              |

---

## Installation

```bash
python -m venv .venv
# Windows: .venv\Scripts\activate   |   macOS/Linux: source .venv/bin/activate
pip install -r requirements.txt -r requirements-dev.txt
```

> First run of the app downloads the embedding model (~90 MB) once, then caches it locally.

## Environment setup

Configuration has sensible local defaults, so the app runs with no setup. To override
anything, copy the template and edit:

```bash
cp .env.example .env
```

Key settings (all centralized in [`app/config/settings.py`](app/config/settings.py)):
`EMBEDDING_MODEL_NAME`, `TOP_K`, `SIMILARITY_THRESHOLD_HIGH/LOW`, `DB_PATH`, `INDEX_DIR`,
`LOG_LEVEL`. **Similarity thresholds require empirical tuning** against your own FAQs.

## Quick start

With the virtual environment activated, from the project root:

```bash
python scripts/initialize_database.py --with-sample
```
Creates the SQLite schema and loads the 30 sample FAQs.

```bash
python scripts/rebuild_index.py
```
Builds the FAISS index from the active FAQs (also happens automatically on first app launch).

```bash
streamlit run app/main.py
```
Opens the app. Use the sidebar to switch between **Chat** and **Admin**, and toggle
**Developer mode** to see retrieval diagnostics.

Handy extras:

```bash
python scripts/import_faqs.py path/to/your.csv   # import your own FAQs
python scripts/rebuild_index.py --status         # inspect index/DB consistency
```

## Sample questions to try

- "I can't remember my login password" → password reset FAQ (high confidence)
- "how do I get my money back" → refund FAQ
- "where is my parcel" → order tracking FAQ
- "what's the meaning of life" → honest fallback (logged for admin review)

## How confidence handling works

Each match has a cosine-similarity score in roughly `0.0–1.0`. Two thresholds split matches
into three bands:

| Score | Band | Behavior |
|-------|------|----------|
| `≥ SIMILARITY_THRESHOLD_HIGH` (0.65) | High | Return the curated answer normally |
| `≥ SIMILARITY_THRESHOLD_LOW` (0.45) | Medium | Return the answer with a soft caveat |
| `< SIMILARITY_THRESHOLD_LOW` | Low | **Do not** answer — show a fallback and log the question |

The bot never fabricates an answer: a weak match yields a fallback plus suggested related
topics, and the question is stored in `unanswered_questions` for the admin to review. Tune
the thresholds in `.env` against your own data and the feedback log.

## Troubleshooting

- **`python` opens the Microsoft Store / "Python was not found" (Windows):** the Store alias
  stubs shadow real Python. Use your actual interpreter (e.g. a conda `python.exe`) to create
  the venv, then activate `.venv` and use `python` from there.
- **`conda create` fails with `CondaSSLError` / certificate verify failed:** your network
  inspects TLS and conda can't verify the Anaconda repo. This project uses `pip` + PyPI
  instead — create a `.venv` and `pip install -r requirements.txt` (pip ships its own CA
  bundle and works here).
- **`pip install` is slow with repeated `pypi.ngc.nvidia.com` retries:** a global pip config
  adds that as an extra index; it fails DNS and pip falls back to PyPI. It's harmless but
  slow. To skip it for one run: `pip install --index-url https://pypi.org/simple ...`, or
  remove the `extra-index-url` line from your pip config.
- **First launch is slow:** the embedding model downloads once (~90 MB) and is cached
  thereafter.
- **Slow model load with repeated `huggingface.co` SSL retries:** the same TLS inspection
  blocks Hugging Face's update check. Once the model is cached, set `HF_OFFLINE=1` in `.env`
  to load from cache only and skip the network entirely (instant load).
- **Chat says the index isn't built:** open **Admin → Index → Rebuild index now**, or run
  `python scripts/rebuild_index.py`.

---

## Roadmap (build phases)

1. **Foundation** — structure, config, logging, deps
2. **SQLite** — schema, repository/CRUD, feedback + unanswered logs, sample data
3. **Embeddings** — cached model, batch embedding, normalization
4. **FAISS** — index build, id-mapping, persistence, consistency validation, top-k
5. **Retrieval service** — `answer_question()` with confidence logic
6. **Streamlit UI** — chat page + admin page
7. **Tests** — DB, embeddings, retrieval, index consistency, confidence, feedback
8. **Documentation** — README, concept explainers, troubleshooting

### Future versions (designed for, not built in V1)

```text
V1  SQLite + FAISS  →  V2  feedback analytics + better retrieval
                   →  V3  PDF/document ingestion
                   →      optional Chroma or another vector DB
                   →  V4  local LLM (Ollama) + RAG
```

---

## Project structure

```text
app/
  main.py                 Streamlit entrypoint
  config/                 centralized settings + logging
  database/               SQLite: connection, schema, repository   (Phase 2)
  embeddings/             sentence-transformers wrapper            (Phase 3)
  retrieval/              FAISS index + search                     (Phase 4-5)
  services/               FAQ / feedback / admin services          (Phase 5)
  ui/                     chat + admin pages                       (Phase 6)
data/                     sample FAQs, SQLite db, FAISS indexes
scripts/                  initialize_database / import_faqs / rebuild_index
tests/                    pytest suite                             (Phase 7)
```

## Testing

```bash
pytest
```

## License

MIT — see [LICENSE](LICENSE).
