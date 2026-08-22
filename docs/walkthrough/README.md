# Semantic FAQ Chatbot — Code Walk-Through

**A guided, presentation-style tour of the whole codebase, written for complete
beginners who want to reach real mastery — not just "run it," but understand
*why* every piece is shaped the way it is.**

You do not need prior experience with embeddings, vector search, or Streamlit.
Each concept is introduced from zero, shown in the actual code, and reinforced
with footnotes, pitfalls, and small exercises.

---

## How this walk-through is organized

The tour follows the **path a question travels** through the system — UI →
embeddings → FAISS → SQLite → answer — because understanding the flow is the
fastest route to understanding the parts.

Each chapter is a **mini-presentation**: it is split into "slides" separated by a
horizontal rule (`───`). Every slide ends with a **Footnotes** block that defines
jargon, explains the reasoning, flags pitfalls, and points to further reading. Read
them — the footnotes are where the nuance lives.

> **📺 Live slides:** the decks are published to GitHub Pages on every push —
> **[view them online](https://kalyancn4u.github.io/faq-chatbot/)** (combined deck +
> one per chapter). See [`.github/workflows/pages.yml`](../../.github/workflows/pages.yml).

> **Two ways to read it**
> 1. **As a document** (recommended first pass): just scroll — it reads top to
>    bottom like a book with slide breaks.
> 2. **As slides** (for teaching/presenting): build every chapter — plus one
>    combined deck — into self-contained HTML with the included script:
>    ```bash
>    ./scripts/build_slides.ps1     # Windows (PowerShell);  add -Pdf for PDFs
>    ./scripts/build_slides.sh      # macOS/Linux;           add --pdf for PDFs
>    ```
>    Decks land in `docs/walkthrough/slides/` — right beside these chapters
>    (open `walkthrough-full.html`). The script
>    injects Marp front-matter into temporary copies, so the source files stay
>    clean for GitHub. **Requires [Node.js](https://nodejs.org)** (Marp CLI is
>    fetched automatically via `npx`).

---

## The learning path (read in order)

| # | Chapter | What you'll master |
|---|---------|--------------------|
| 1 | [The Big Picture](01-big-picture.md) | The architecture, the four core concepts (embedding, semantic search, vector index, system of record), and the design laws that hold everything together |
| 2 | [Configuration & Logging](02-configuration-and-logging.md) | Why *all* settings live in one place, frozen dataclasses, environment overrides, and consistent logging |
| 3 | [The Database Layer](03-the-database-layer.md) | SQLite as the source of truth: schema, the repository pattern, parameterized queries, soft-delete, and safe CSV import |
| 4 | [Embeddings](04-embeddings.md) | What an embedding *is*, cosine similarity, normalization, and why the model is loaded once and cached |
| 5 | [FAISS & the Index](05-faiss-and-the-index.md) | Vector search, the derived-artifact idea, the FAISS↔SQLite id map, atomic rebuilds, the consistency invariant — **+ Appendix A: "Why not Chroma?"** |
| 6 | [Retrieval & Confidence](06-retrieval-and-confidence.md) | The service layer, confidence bands, honest fallbacks, and *why V1 never hallucinates* |
| 7 | [Channels & Formatting](07-channels-and-formatting.md) | Tailoring one answer to Chat/WhatsApp/Telegram/SMS, MarkdownV2 escaping, and SMS segments |
| 8 | [The Streamlit UI](08-the-streamlit-ui.md) | Streamlit's rerun model, `cache_resource`, `session_state`, and safe, responsive HTML rendering |
| 9 | [Testing & Quality](09-testing-and-quality.md) | How the tests are structured, fast fixtures, and testing ML code without brittleness |
| 10 | [Mastery: End-to-End & Exercises](10-mastery-end-to-end.md) | A full trace of one query through every layer, extension projects, and a self-assessment |

**Reference:** [Glossary of terms](GLOSSARY.md) — every piece of jargon, defined
plainly, cross-linked from the footnotes.

---

## Conventions used throughout

- **Code excerpts are illustrative**, often trimmed for focus. Each links to the
  real file so you can read it in full — e.g. [settings.py](../../app/config/settings.py).
- Inline markers like `[1]` point to the bulleted **Footnotes** block at the bottom of
  that same slide (one bullet per reference).
- 🧠 **Nuance** callouts highlight a subtle "why." ⚠️ **Pitfall** callouts warn of a
  common mistake. 🛠️ **Try it** callouts are hands-on exercises.
- Terms in **bold italic** like ***embedding*** are defined in the [Glossary](GLOSSARY.md).

---

## Before you start (optional but helpful)

You'll get the most out of the tour if the app runs locally. From the project root:

```bash
python scripts/initialize_database.py --with-sample
python scripts/rebuild_index.py
streamlit run app/main.py
```

If any of that is unfamiliar, the main [project README](../../README.md) has the
full setup, and Chapter 1 explains what each step does.

---

*This walk-through documents the code as of Version 1. It pairs with the reader-facing
[README](../../README.md) and the [channels guide](../CHANNELS.md). Want to build a
walk-through like this for your own project? See the
[build-it-yourself playbook](../../instructions_ppt.md).*
