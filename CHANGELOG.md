# Changelog

All notable changes to this project are documented here.
Format based on [Keep a Changelog](https://keepachangelog.com/); this project aims to
follow [Semantic Versioning](https://semver.org/).

## [1.0.0] — 2026-08-22

First working version: a local‑first **Semantic FAQ Chatbot**, plus a full
**code walk‑through** (docs + HTML slide decks + a live GitHub Pages site) and
reusable playbooks for building such walk‑throughs.

### Added — Application (Version 1)
- **Local‑first architecture**, CPU‑only, no cloud/API/LLM: Streamlit UI →
  Sentence‑Transformers embedding → FAISS semantic search → SQLite (system of record)
  → confidence handling.
- **SQLite layer** — `connection`/`schema`/`repository`/`csv_import`: `faqs`,
  `feedback`, `unanswered_questions` tables; parameterized queries; soft‑delete;
  FK cascade; 30 sample FAQs with paraphrases.
- **Embeddings** — cached `all-MiniLM-L6-v2` (configurable), L2‑normalized `float32`,
  lazy model load.
- **FAISS index** — exact `IndexFlatIP` (cosine), FAISS↔SQLite id map, atomic rebuild,
  consistency invariant (`#vectors == #ids == #active FAQs`), staleness detection.
- **Retrieval service** — `answer_question()` returning a typed `AnswerResult` with
  three confidence bands (High/Medium/Low); honest fallback (never hallucinates);
  logs unanswered questions.
- **Streamlit UI** — chat page (answer, confidence badge, alternatives, 👍/👎 feedback,
  fallback) and admin page (FAQ CRUD, CSV import/export, index rebuild + status,
  unanswered review, feedback view); safe destructive actions.
- **Channel‑aware reply formatting** — `response_formatter`: tailors each reply to
  Chat window / WhatsApp / Telegram (MarkdownV2 escaping) / SMS (160‑char segments);
  sidebar “Reply format” selector previews the reply as‑sent; the preview and the
  developer‑diagnostics table **wrap and stay responsive**.
- **Config & logging** — centralized, env‑overridable `settings`; one‑time logging setup.
- **Tests** — 44 pytest tests (DB, embeddings, index consistency, retrieval,
  confidence, channel formatting, UI helpers); fast fixtures; no brittle float asserts.
- **CLI scripts** — `initialize_database`, `import_faqs`, `rebuild_index`.

### Added — Code walk‑through & presentation
- **`docs/walkthrough/`** — 10 chapters (data‑flow ordered) + `GLOSSARY.md` + a
  landing `README.md`, written beginner‑to‑mastery with per‑slide footnotes,
  callouts, and exercises; every code block names its source file.
- **Chapter 5 Appendix A — “Why not Chroma?”** (SQLite + FAISS vs a vector database).
- **Architecture diagram** — self‑contained `assets/architecture.svg` (theme‑safe),
  with a plain‑text alternative on its own slide.
- **Marp slide decks** — `scripts/build_slides.sh` / `.ps1` render each chapter plus a
  combined deck to self‑contained HTML; `.marprc.yml` (`breaks: false`).
- **Design system** — `assets/marp-theme.css`: minimal/functional; **auditorium type
  scale**, **WCAG 2.2 AA contrast**, single accent hue, h2 hairline underline, code
  cards, clean tables, and a muted **bulleted footnotes** citation band.
- **GitHub Pages publishing** — `.github/workflows/pages.yml` builds + deploys on push;
  live at <https://kalyancn4u.github.io/faq-chatbot/>.
- **Playbooks** — `instructions_ppt.md` (narrated “how this was built”) and
  `instructions_codewalk.md` (portable, repo‑agnostic kit); linked from `README.md`
  and `instructions.md`.
- **Docs** — full `README.md` (with a Code Walk‑Through section), `docs/CHANNELS.md`,
  `instructions.md` (project spec).

### Changed
- Reply preview and diagnostics table moved from `st.code`/`st.table` to wrapping,
  responsive HTML (fixes horizontal overflow; literal rendering of `*`/`\`).
- Slide type scale enlarged for large‑room legibility; footnotes converted from a
  running paragraph to a **bulleted list, one bullet per reference**.

### Fixed
- **Slide overflow** — compact‑but‑legible sizing + a taller 1280×940 slide + scoped
  `diagram-text`/`dense` escape hatches → 0 slides overflow.
- **Footnotes wrapping early** — `breaks: false` (Marp’s default `true` turned the
  source’s hard wraps into `<br>`), letting text flow to the full slide width.
- **WCAG contrast** — secondary greys darkened (a `#8a929c` label was ~3.2:1 → now ~5.7:1).
- **Dark‑mode readability** — pinned the deck light (`color-scheme: light`) so the
  imported theme’s `light-dark()` can’t put dark text on a dark slide.
- **Broken diagram in decks** — Marp doesn’t inline `<img>`; build now copies
  `assets/*.svg` next to the decks.
- **Build reliability** — `--no-stdin` (Marp hung waiting on stdin off‑TTY); PowerShell
  reads sources as UTF‑8 and stays ASCII‑only (mojibake) and judges Marp by exit code.

### Environment notes
- Real Python is Miniconda at `D:\tools\miniconda3` (the PATH `python` is a Store stub);
  project deps live in a repo‑local **`.venv`** (conda installs fail on this network’s TLS
  interception — `pip`/PyPI works). `HF_OFFLINE=1` in `.env` loads the cached model
  without hitting Hugging Face. Slide builds need **Node.js** (Marp CLI).

[1.0.0]: https://github.com/kalyancn4u/faq-chatbot
