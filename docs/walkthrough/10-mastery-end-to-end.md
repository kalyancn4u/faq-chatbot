# Chapter 10 — Mastery: End-to-End & Exercises

*One query traced through every layer, then projects and a self-check to lock it in.*

**By the end of this chapter you will be able to:** trace a real question through the
entire codebase from memory, extend the system confidently, and assess your own
understanding.

---

## The full journey of one question

Let's follow **"I can't remember my login password"** from keypress to reply. Match
each step to its chapter.[1]

```text
1. UI            chat.py reads the text, calls FAQService.answer_question(...)     (Ch 8)
2. Service       strips/validates input, asks SemanticSearch for candidates       (Ch 6)
3. Embedding     the query becomes a normalized 384-dim vector                    (Ch 4)
4. FAISS         IndexFlatIP returns nearest positions + cosine scores            (Ch 5)
5. Id map        positions → SQLite faq_ids                                       (Ch 5)
6. SQLite        each id is hydrated to its real, active FAQ record               (Ch 3)
7. Confidence    best score 0.92 ≥ 0.65 → HIGH → ANSWER_FOUND                     (Ch 6)
8. Result        a typed AnswerResult with answer + alternatives                  (Ch 6)
9. Format        shaped for the chosen channel (Chat/WhatsApp/Telegram/SMS)       (Ch 7)
10. Render       shown with a confidence badge + feedback buttons                 (Ch 8)
```

Every arrow you learned in Chapter 1 just executed. If you can narrate these ten
steps, you understand the system.[2]

> **Footnotes**
> [1] The two "design laws" both appear here: step 6 fetches truth from SQLite (Law
> #1), and step 7's threshold gate is what would send a *weak* match to a fallback
> instead (Law #2).
> [2] Notice how thin each layer is. No single file is doing everything — which is
> exactly why you *can* hold the whole flow in your head.

---

## The contrasting journey: an off-topic question

Now trace **"what's the meaning of life"**:

```text
3-5. same path → nearest FAQ is something unrelated, score ≈ 0.12
7.   0.12 < 0.45  →  LOW  →  status LOW_CONFIDENCE
8.   answer = FALLBACK_MESSAGE (not the weak match!)                              (Ch 6)
8b.  question written to unanswered_questions for admin review                   (Ch 6)
10.  user sees an honest fallback + suggested topics
```

Same machinery, opposite outcome — and **no hallucination**. The only difference is
which side of the threshold the score lands on.[1]

> **Footnotes**
> [1] Sit with this: the *entire* safety guarantee of V1 is "compare a number to a
> threshold and return canned text if it's too low." Simple mechanisms, rigorously
> applied, beat complex ones you can't reason about.

---

## Where each concept lives (a memory map)

| Concept | File(s) | Chapter |
|---------|---------|---------|
| Config, thresholds, paths | `app/config/settings.py` | 2 |
| Truth: FAQs, feedback, logs | `app/database/` | 3 |
| Text → vectors | `app/embeddings/embedder.py` | 4 |
| Vector search + id map | `app/retrieval/faiss_index.py`, `index_manager.py` | 5 |
| Candidates + confidence | `app/retrieval/search.py`, `app/services/faq_service.py` | 6 |
| Channel formatting | `app/services/response_formatter.py` | 7 |
| Pages + widgets | `app/main.py`, `app/ui/` | 8 |
| Proof it works | `tests/` | 9 |

🧠 **Nuance:** this table *is* the architecture. If you can place a new requirement
into the right row before writing code, you've internalized the design.

---

## Extension projects (from easy to ambitious)

Learn by changing it. Each project names the files you'd touch:[1]

1. **Tune thresholds** — set `SIMILARITY_THRESHOLD_HIGH/LOW` in `.env`, ask real
   questions, read the feedback log, iterate. *(config only)*
2. **Add a category filter** — let the chat restrict search to one category. *(add a
   repo query + a UI selectbox + pass it through the service)*
3. **Add a Slack channel** — one enum value + one `ChannelSpec` + one list entry.
   *(response_formatter.py; add a test)*
4. **Swap the model** — set `EMBEDDING_MODEL_NAME` to a multilingual model and add a
   few non-English FAQs. *(config + data; rebuild the index)*
5. **Actually send to Telegram** — a small sender using the Bot API with
   `parse_mode=MarkdownV2` and the existing `escape_markdown_v2`. *(new module +
   secrets handling)*
6. **Add RAG (advanced)** — introduce a local LLM that writes answers *grounded in*
   retrieved FAQs, behind the service seam, with citations. *(new service; keep the
   confidence gate)*

> **Footnotes**
> [1] Notice how the architecture makes each project *local*: a change lands in one or
> two files because responsibilities are separated. If a "small" change forces edits
> everywhere, that's a design smell — not the case here, by design.

---

## Self-assessment (can you answer these?)

If you can answer all of these without looking, you've reached mastery:[1]

1. Why is FAISS a *derived* artifact, and what follows from that?
2. What does L2-normalization buy us, and how does it connect Chapters 4 and 5?
3. State the consistency invariant. What happens if it's violated?
4. Why can't Version 1 hallucinate? Point to the exact branch in the code.
5. Why does the UI store the `AnswerResult` rather than formatted text?
6. Why must Telegram text be escaped, and where does the code do it?
7. Why do we test "paraphrase closer than unrelated" instead of an exact score?

> **Footnotes**
> [1] Struggling with one? It names the chapter to revisit: 1→Ch5/1, 2→Ch4, 3→Ch5,
> 4→Ch6, 5→Ch7/8, 6→Ch7, 7→Ch9. Teaching a concept to someone else is the final
> test of understanding — try explaining #4 aloud.

---

## Principles worth carrying to your next project

This codebase is small, but the ideas generalize:[1]

- **One source of truth** — for config *and* for data *and* for behavior.
- **Separate responsibilities** — UI, services, data, search each do one thing.
- **Fail loud, never silent** — validate invariants; refuse to serve wrong results.
- **Derive, don't duplicate** — rebuild the index from truth; don't hand-sync.
- **Design for testability** — pure functions and injected dependencies.
- **Simple → Correct → Tested → Maintainable → Extensible** — in that order.

> **Footnotes**
> [1] These aren't specific to chatbots. They're how you keep *any* system
> understandable as it grows. The best code is not the cleverest — it's the code the
> next person (often future-you) can reason about.

---

## Recap — you made it

You can now trace a question through every layer, place any change in the right file,
extend the system, and articulate *why* each decision was made. That's mastery — not
memorizing the code, but understanding the ideas it expresses.

**Back to:** [Walk-through index](README.md) · [Project README](../../README.md) ·
[Glossary](GLOSSARY.md)
