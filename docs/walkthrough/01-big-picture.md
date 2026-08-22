# Chapter 1 — The Big Picture

*How the whole system fits together, and the ideas everything else depends on.*

**By the end of this chapter you will be able to:** explain what the app does,
name the four core concepts it is built on, read the architecture diagram, and
state the two "design laws" that keep the system correct.

---

## What are we building?

A **FAQ chatbot** that answers a user's question with a *curated* answer from a
knowledge base — and understands **meaning**, not just keywords.[1]

All of these should find the *same* password FAQ:

- "How do I reset my password?"
- "I forgot my password."
- "I can't remember my login credentials."

The hard part is that the last one shares almost no words with the first. Keyword
search would fail; **semantic search**[2] succeeds.

> **Footnotes**
> [1] *Curated* means a human wrote the answer and stored it. The bot **retrieves**
> it; it does not **generate** new text. This is a deliberate Version-1 choice —
> see Chapter 6 for why "no generation" prevents hallucination.
> [2] ***Semantic search*** = searching by meaning. We turn text into numbers that
> capture meaning (an *embedding*), then find stored questions whose numbers are
> closest. Defined fully in [Chapter 4](04-embeddings.md).

---

## The four core concepts (the whole app in four words)

1. ***Embedding*** — a model turns a sentence into a list of numbers (a *vector*)
   that represents its meaning.[1]
2. ***Vector index*** — a data structure (FAISS) that, given a query vector, finds
   the nearest stored vectors *fast*.[2]
3. ***System of record*** — the authoritative store of the real data (SQLite): the
   questions, answers, categories, feedback, and logs.[3]
4. ***Confidence handling*** — deciding whether the best match is *good enough* to
   show, or whether to fall back honestly.

Everything in the codebase is an implementation detail of one of these four ideas.

> **Footnotes**
> [1] A *vector* here is just a fixed-length array of floats, e.g. 384 numbers for
> our model. "Similar meaning → nearby vectors" is the entire trick.
> [2] "Fast" matters at scale, but even for a few thousand FAQs a good index keeps
> the UI instant. We use an **exact** index (no approximation) — Chapter 5.
> [3] "System of record" is a data-architecture term for *the* trusted copy. If two
> stores ever disagree, this one wins. Here, FAISS is rebuilt from SQLite — never
> the other way around.

---

## The architecture, as data flows

![Architecture of the Semantic FAQ Chatbot: a question flows from the user through the Streamlit UI, the Sentence Transformer (embedding), FAISS (nearest vectors), and SQLite (authoritative answer), then through confidence handling and channel formatting to a reply. Design Law #1: FAISS is a derived index rebuilt from SQLite. Design Law #2: a weak match never becomes an answer.](assets/architecture.svg)

Read it top to bottom: that arrow is *exactly* the journey each chapter zooms into.[1]
A plain-text version is on the next slide (screen-reader and terminal friendly).[2]

> **Footnotes**
> [1] Notice the split of responsibilities: **embeddings** understand language,
> **FAISS** finds candidates, **SQLite** holds truth, **services** make decisions,
> **UI** presents. This separation is not decoration — it is what makes each part
> testable and replaceable (Chapter 9).
> [2] Same information, two forms — the diagram for a quick visual grasp, the text
> for accessibility and copy-paste. Separate slides keep each one legible.

---

## The architecture — text version

<!-- _class: diagram-text -->

*The same flow as the diagram, in plain text:*

```text
   User types a question
            │
            ▼
     ┌──────────────┐
     │  Streamlit UI │   (app/ui/)            Chapter 8
     └──────────────┘
            │ question text
            ▼
  ┌────────────────────┐
  │ Sentence Transformer│  (app/embeddings/)  Chapter 4
  │  → query embedding  │
  └────────────────────┘
            │ 384-dim vector (normalized)
            ▼
     ┌──────────────┐
     │    FAISS      │   (app/retrieval/)     Chapter 5
     │ nearest match │
     └──────────────┘
            │ faq_id + similarity score
            ▼
     ┌──────────────┐
     │    SQLite     │   (app/database/)      Chapter 3
     │ authoritative │
     │  answer text  │
     └──────────────┘
            │ FAQ record
            ▼
  ┌────────────────────┐
  │ Confidence handling │  (app/services/)    Chapter 6
  │ answer | fallback   │
  └────────────────────┘
            │
            ▼
   Formatted for the chosen channel (app/services/response_formatter.py)  Chapter 7
```

> **Footnotes**
> [1] Each box names the responsible package and its chapter, so you can trace the
> flow straight into the code: `app/ui/` (Ch 8) → `app/embeddings/` (Ch 4) →
> `app/retrieval/` (Ch 5) → `app/database/` (Ch 3) → `app/services/` (Ch 6–7).

---

## Design Law #1 — SQLite is truth; FAISS is derived

The FAISS index is a **derived artifact**[1]: it can always be rebuilt from the
active rows in SQLite. This single rule has big consequences:

- If the index is lost or corrupted, you **rebuild** it — no data is lost.
- Answers are always fetched from SQLite after FAISS points at them, so a stale
  index can never surface a deleted or edited answer.[2]
- The mapping "FAISS row ↔ SQLite id" must be kept consistent — Chapter 5 is
  largely about doing this safely.

🧠 **Nuance:** FAISS stores *vectors and positions*, not text. It literally cannot
return an answer on its own; it returns *where* the answer is.

> **Footnotes**
> [1] ***Derived artifact*** = something computed from a source of truth, like a
> compiled binary from source code. You never edit it by hand; you regenerate it.
> [2] The retrieval code re-checks each hit against SQLite and skips any FAQ that is
> missing or deactivated. See `SemanticSearch.search` in
> [search.py](../../app/retrieval/search.py) — covered in Chapter 6.

---

## Design Law #2 — Never present a weak match as an answer

The bot does **not** blindly return the nearest match. A similarity **score**[1]
is compared to two thresholds, producing three outcomes:

| Score | Band | What the user sees |
|-------|------|--------------------|
| high (≥ 0.65) | **High** | the curated answer, confidently |
| medium (≥ 0.45) | **Medium** | the answer, with a gentle caveat |
| low (< 0.45) | **Low** | an honest fallback + suggestions; question logged |

This is why Version 1 **cannot hallucinate**: the worst case is "I couldn't find a
reliable answer," never a made-up one.[2]

⚠️ **Pitfall:** those thresholds (0.65 / 0.45) are **starting points, not universal
truths.** They must be tuned against *your* data — see Chapter 6 and the footnote.[3]

> **Footnotes**
> [1] The ***score*** is *cosine similarity*, ranging ~0–1 for this model. 1.0 =
> identical direction (same meaning); ~0 = unrelated. Chapter 4 explains why.
> [2] Compare this to a Large Language Model (LLM) that *generates* text: it can
> produce fluent but false answers. Retrieval-only trades flexibility for safety —
> the right trade for an FAQ bot. Generation is a possible *future* version.
> [3] Thresholds depend on your model, your writing style, and how similar your FAQs
> are to each other. The honest way to set them is empirical: run real questions,
> read the feedback log, adjust. Never treat a magic number as gospel.

---

## What is deliberately *not* here (and why)

Version 1 stays small on purpose. It does **not** use:[1]

- a cloud database, a paid API, or a GPU (it runs on a normal laptop CPU),
- an LLM (retrieval only — see Design Law #2),
- Chroma or another vector database (SQLite + FAISS is simpler and more
  transparent for a focused FAQ app).[2]

The architecture is *designed* so these can be added later (document ingestion,
RAG, a local LLM, an API, Docker) — but adding them now would be premature.[3]

> **Footnotes**
> [1] "Simple → Correct → Tested → Maintainable → Extensible" is the project's
> priority order. Every "no" above is an application of it.
> [2] ***Chroma*** is a vector database that bundles storage + search. It shines for
> large document/RAG systems. For a curated FAQ set, keeping SQLite and FAISS
> separate makes the data flow easy to *see* — which is exactly what a learner
> needs. It's an easy future swap behind the retrieval layer. The full answer to
> *"why not Chroma?"* is [Appendix A of Chapter 5](05-faiss-and-the-index.md).
> [3] ***RAG*** = Retrieval-Augmented Generation: retrieve relevant text, then let an
> LLM write an answer grounded in it. That's a natural Version 4. The clean service
> seam in Chapter 6 is where it would plug in.

---

## Recap & what's next

- The app answers questions by **meaning**, using embeddings + FAISS, with SQLite
  as the source of truth.
- **Law #1:** FAISS is derived from SQLite. **Law #2:** weak matches never become
  answers.
- Version 1 is intentionally minimal and local-first.

🛠️ **Try it:** open the app, turn on **Developer mode** (sidebar), and ask
"I can't remember my password." Watch the matched FAQ, the score, and the
confidence band — you're seeing all four core concepts at once.

**Next:** [Chapter 2 — Configuration & Logging](02-configuration-and-logging.md),
where we start reading real code, beginning with the one place every setting lives.
