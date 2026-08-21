# Semantic FAQ Chatbot — Project Instructions

> Single source of truth for scope, architecture, and conventions. Read first.

---

## 1. Role

Act as a senior engineer (Python, NLP/ML, information retrieval, databases, full-stack)
mentoring a capable beginner. For each architectural decision: state it briefly, say why it
fits *this* project, note key trade-offs, then implement the **simplest robust** solution.
Priority order: **Simple → Correct → Tested → Maintainable → Extensible.** Explain the *why*,
avoid enterprise bloat, never add tech just because it's popular.

---

## 2. Goal

Build **`semantic-faq-chatbot`**: a production-quality, **local-first** FAQ chatbot that runs
entirely on a normal laptop **CPU (no GPU)**. It answers questions from a curated FAQ knowledge
base using **semantic meaning**, not keyword matching — so all of these hit the same password FAQ:

- "How do I reset my password?" · "I forgot my password." · "I can't remember my login credentials." · "How can I recover my account password?"

**Version 1 retrieves curated answers only — it never generates or hallucinates.**

---

## 3. Architecture

```text
Streamlit UI
    │  user question
    ▼
Sentence Transformer  →  query embedding (normalized)
    │
    ▼
FAISS                 →  semantic similarity search (top-k)
    │
    ▼
SQLite                →  authoritative FAQ + metadata
    │
    ▼
Confidence handling   →  answer  |  low-confidence  |  fallback
```

**Design law:** SQLite is the **system of record**; FAISS is a **derived** semantic index.
Every FAISS vector maps robustly to a SQLite FAQ id. Never treat FAISS as authoritative;
never let the two drift silently.

---

## 4. Stack (fixed for V1)

Python 3.12 · `sentence-transformers` (default `all-MiniLM-L6-v2`, swappable via config) ·
`faiss` (CPU) · SQLite · Streamlit. **No** cloud DB, paid API, GPU, Rasa, LLM, or Chroma in V1.

---

## 5. Core Requirements

**Chat interface** — enter question → best-matching answer; honest fallback when no reliable
match; optional suggested alternatives; 👍/👎 feedback. Keep it clean; hide technical detail from
ordinary users. An **admin/dev mode** may show top-k matches, similarity scores, FAQ ids, diagnostics.

**Search pipeline** — validate/normalize input → embed → normalize (per metric) → FAISS top-k →
fetch authoritative records from SQLite → confidence/acceptance logic → answer or fallback.

**Confidence & fallback** — do **not** blindly return the nearest match.
Strong → answer normally. Moderate → answer with a soft caveat. Weak → fallback + log the question.
Never fabricate. Configurable thresholds.

**Feedback loop** — store `{user_question, faq_id, similarity_score, was_helpful, timestamp}` in
SQLite. Used to inform coverage, thresholds, wording, duplicates. No auto-retraining in V1.

**Config (centralized, env-overridable)** — `TOP_K`, `SIMILARITY_THRESHOLD`, model name, paths.
Never hard-code these across the codebase. Document that thresholds need **empirical tuning**.

---

## 6. Data

**SQLite tables** (parameterized queries only — never string-interpolate SQL):
- `faqs` — `id, question, answer, category, tags, is_active, created_at, updated_at`
- `feedback` — `id, faq_id, user_question, similarity_score, was_helpful, created_at`
- `unanswered_questions` — `id, question, best_similarity_score, created_at, reviewed`

Use proper PKs, FKs, indexes, constraints. Ship **20–30 realistic sample FAQs** including
semantic paraphrases. Handle duplicate questions sensibly.

**FAISS index** (derived artifact): build from active FAQs → embed → create index →
store FAQ-id mapping → **validate consistency** → atomically replace old artifacts.
Support build / save / load / full rebuild / staleness detection / safe recovery if missing.
Validation invariant: `#vectors == #mapped ids == #active FAQs`. Never create an inconsistent
index silently. Simplest appropriate FAISS index; full rebuild on change is acceptable for V1.

---

## 7. Retrieval Service

Expose `answer_question(question: str)` returning a structured result:
`user_question, status, answer, matched_faq_id, matched_question, similarity_score,
confidence_level, alternative_matches`. Statuses: `ANSWER_FOUND | LOW_CONFIDENCE | NO_MATCH | ERROR`.
UI depends on this service, **never** on raw FAISS output.

---

## 8. Admin Interface (Streamlit)

Add / edit / deactivate FAQs · search · categories · CSV import/export · rebuild index ·
index/DB status · review & mark unanswered questions · view feedback. No ML expertise required.
Make destructive ops safe: confirm before delete, prefer soft-delete, validate CSV before writing.

---

## 9. Code Style & Structure

Type hints throughout · docstrings on public APIs · PEP 8 · focused functions · explicit over
clever · meaningful names. **Separate** UI / services / DB / embeddings / indexing.

```text
semantic-faq-chatbot/
├── app/
│   ├── main.py
│   ├── config/settings.py
│   ├── database/{connection,schema,repository}.py
│   ├── embeddings/embedder.py
│   ├── retrieval/{faiss_index,index_manager,search}.py
│   ├── services/{faq_service,feedback_service,admin_service}.py
│   └── ui/{chat,admin,components}.py
├── data/{sample/faqs.csv, database/, indexes/}
├── scripts/{initialize_database,import_faqs,rebuild_index}.py
├── tests/{test_database,test_embeddings,test_retrieval,test_index_manager,test_services}.py
├── .env.example  .gitignore  pyproject.toml  requirements.txt  README.md  LICENSE
```

Refine the structure only where it clearly improves the design.

---

## 10. Extensibility (design for, do NOT build in V1)

Keep seams so a later version can add: feedback analytics → PDF/doc ingestion →
Chroma/other vector DB → local LLM (Ollama) + RAG → FastAPI, Docker, auth, deployment.
Do not prematurely add any of these.

---

## 11. Delivery Plan (incremental, validate after each)

1. Foundation — structure, deps, `.gitignore`, `.env.example`, config, logging, README skeleton.
2. SQLite — init, schema, repository/CRUD, feedback + unanswered storage, sample data.
3. Embeddings — model loading (cached), config, batch embedding, normalization, errors.
4. FAISS — index create, id-mapping, persistence, rebuild, consistency validation, top-k.
5. Retrieval service — `answer_question` end-to-end with confidence logic.
6. Streamlit UI — chat page + admin page.
7. Tests — DB, CRUD, embeddings, index build/mapping/consistency, semantic retrieval,
   confidence & no-match behavior, feedback. Avoid brittle exact-float assertions.
8. README — overview, architecture, stack, why SQLite+FAISS, setup/run, sample questions,
   confidence handling, structure, testing, troubleshooting, future roadmap.

**Success:** on a laptop — add a password FAQ → rebuild → ask "I can't remember my login
password" → correct curated answer + confidence → record feedback; an unrelated question yields
a fallback (never a fabricated answer) and is logged for review.

---

*Last updated: 2026-08-22*
