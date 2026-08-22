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

## 📚 Learn the codebase — Code Walk-Through

New here, or want to truly understand *how* and *why* this works? Start with the
**[Code Walk-Through](docs/walkthrough/README.md)** — a guided, presentation-style tour
written for complete beginners, taking you from "what's an embedding?" to mastery of
every layer. Each chapter follows the path a question travels through the system, with
extensive footnotes, pitfalls, and hands-on exercises on every page.

- **[▶ Start the walk-through](docs/walkthrough/README.md)** — the landing page: learning
  path, how to read it (as a doc *or* as slides), and conventions.
- **[📺 View the slides online](https://kalyancn4u.github.io/faq-chatbot/)** — the decks,
  auto-published to GitHub Pages on every push (combined deck + one per chapter).
- **[📖 Glossary](docs/walkthrough/GLOSSARY.md)** — every term (embedding, cosine, FAISS,
  invariant, soft-delete…) defined in plain language.
- **[🛠️ Build-it-yourself playbook](instructions_ppt.md)** — `instructions_ppt.md`: the
  narrated how-and-why of building a walk-through like this (structure, the Marp design system,
  the build pipeline, overflow discipline, WCAG-aware type/contrast, and publishing).
- **[📦 Portable kit for *any* repo](instructions_codewalk.md)** — `instructions_codewalk.md`:
  a self-contained, repo-agnostic recipe with the exact theme CSS, `.marprc.yml`, build script,
  and Pages workflow — drop it into any project to generate the markdown docs, the HTML decks,
  and a live `github.io` site.

**Read it, present it, or build the decks yourself:**

```bash
./scripts/build_slides.ps1     # Windows (PowerShell);  add -Pdf for PDFs
./scripts/build_slides.sh      # macOS/Linux;           add --pdf for PDFs
```
Decks land in `docs/walkthrough/slides/` — right next to their source (open `walkthrough-full.html`). Requires [Node.js](https://nodejs.org).

<details>
<summary><b>The ten chapters (click to expand)</b></summary>

| # | Chapter | You'll master |
|---|---------|---------------|
| 1 | [The Big Picture](docs/walkthrough/01-big-picture.md) | Architecture, the four core concepts, and the two design laws |
| 2 | [Configuration & Logging](docs/walkthrough/02-configuration-and-logging.md) | Centralized config, frozen dataclasses, env overrides |
| 3 | [The Database Layer](docs/walkthrough/03-the-database-layer.md) | SQLite, repository pattern, parameterized queries, soft-delete |
| 4 | [Embeddings](docs/walkthrough/04-embeddings.md) | What an embedding is, cosine, normalization, model caching |
| 5 | [FAISS & the Index](docs/walkthrough/05-faiss-and-the-index.md) | Vector search, the id map, atomic rebuild, the consistency invariant — **+ Appendix A: "Why not Chroma?"** |
| 6 | [Retrieval & Confidence](docs/walkthrough/06-retrieval-and-confidence.md) | The service layer, confidence bands, why V1 can't hallucinate |
| 7 | [Channels & Formatting](docs/walkthrough/07-channels-and-formatting.md) | Chat/WhatsApp/Telegram/SMS, MarkdownV2 escaping, SMS segments |
| 8 | [The Streamlit UI](docs/walkthrough/08-the-streamlit-ui.md) | Rerun model, `cache_resource`, `session_state`, safe HTML |
| 9 | [Testing & Quality](docs/walkthrough/09-testing-and-quality.md) | Fixtures, testing ML without brittleness |
| 10 | [Mastery: End-to-End](docs/walkthrough/10-mastery-end-to-end.md) | A full query trace, extension projects, a self-check |

</details>

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

## Reply formats (channels)

The same answer is written differently depending on where it would be sent. Pick a
channel from the sidebar's **Reply format** selector and the chat window previews
the reply exactly as it would arrive:

| Channel | Bold | Emoji | Limit | Notes |
|---------|------|-------|-------|-------|
| Chat window | `**bold**` | ✅ | none | full Markdown (default) |
| WhatsApp | `*bold*` | ✅ | ~4096 | single-asterisk bold |
| Telegram | `*bold*` | ✅ | ~4096 | MarkdownV2 — `. - ( ) ! >` are backslash-escaped |
| SMS | none | ❌ | 160/segment | plain text; confidence + related list dropped to save length |

Switching the selector reformats the whole conversation instantly, so you can
verify each channel. **New to this? Read the full beginner's guide:
[docs/CHANNELS.md](docs/CHANNELS.md).**

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
  services/               FAQ / feedback / admin / response_formatter services
  ui/                     chat + admin pages                       (Phase 6)
data/                     sample FAQs, SQLite db, FAISS indexes
docs/                     CHANNELS.md + walkthrough/ (full code walk-through)
scripts/                  initialize_database / import_faqs / rebuild_index
tests/                    pytest suite                             (Phase 7)
```

## Testing

```bash
pytest
```

## Project docs

- [CHANGELOG.md](CHANGELOG.md) — what shipped, per version.
- [instructions.md](instructions.md) — the project spec (scope, architecture, conventions).
- [instructions_ppt.md](instructions_ppt.md) / [instructions_codewalk.md](instructions_codewalk.md)
  — how the code walk‑through was built, and a portable kit to build one for any repo.
- [instructions.txt](instructions.txt) — a plain‑text handoff to resume work in a new session.

## License

MIT — see [LICENSE](LICENSE).
