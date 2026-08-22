# Chapter 6 — Retrieval & Confidence

*Turning raw matches into a trustworthy answer — or an honest fallback.*

**By the end of this chapter you will be able to:** explain the service layer,
follow the `answer_question` pipeline, describe the three confidence bands, and say
precisely why Version 1 cannot hallucinate.

Files: [`search.py`](../../app/retrieval/search.py),
[`faq_service.py`](../../app/services/faq_service.py).

---

## Two layers: search vs. service

There are two levels above FAISS, each with one job:

1. ***SemanticSearch*** (retrieval) — turns a query into ranked **candidates**,
   *hydrated*[1] with their real content from SQLite.
2. ***FAQService*** (the answering service) — applies **confidence** rules to those
   candidates and decides: answer, caveated answer, or fallback.

Keeping "find candidates" separate from "decide what to do" makes each easy to test
and reason about.[2]

> **Footnotes**
> [1] ***Hydrate*** = fill a bare reference with full data. FAISS gives `(faq_id,
> score)`; the search layer looks each id up in SQLite to attach the question,
> answer, and category.
> [2] This is the ***service layer*** pattern: business decisions live in a service,
> not in the UI and not in the database code. The UI just calls `answer_question`.

---

## SemanticSearch: candidates from truth

```python
# app/retrieval/search.py — SemanticSearch.search
def search(self, conn, query, top_k=None) -> list[SearchCandidate]:
    hits = self._index.search(query, top_k=top_k)     # [(faq_id, score), ...]
    repo = FAQRepository(conn)
    candidates = []
    for faq_id, score in hits:
        faq = repo.get(faq_id)
        if faq is None or not faq.is_active:           # skip stale/deleted
            continue
        candidates.append(SearchCandidate(faq.id, faq.question, faq.answer,
                                          faq.category, score))
    return candidates
```

The crucial line is the skip: even if a **stale index** points at a now-deleted or
deactivated FAQ, we never surface it, because the answer comes from SQLite, not
FAISS.[1]

> **Footnotes**
> [1] This is Design Law #1 doing real work. FAISS is only a *hint* about where to
> look; SQLite has the final say on what exists and is active. A slightly stale index
> can never leak a removed answer.

---

## The result object: one shape the UI can trust

`answer_question` always returns a single structured `AnswerResult`:[1]

```python
# app/services/faq_service.py
@dataclass(frozen=True)
class AnswerResult:
    user_question: str
    status: AnswerStatus            # ANSWER_FOUND | LOW_CONFIDENCE | NO_MATCH | ERROR
    answer: str
    confidence_level: ConfidenceLevel   # High | Medium | Low | None
    matched_faq_id: int | None = None
    matched_question: str | None = None
    similarity_score: float | None = None
    alternative_matches: list[AlternativeMatch] = ...
```

Whatever happens — great match, weak match, no index, empty input — the UI receives
**the same type** and renders it uniformly.[2]

> **Footnotes**
> [1] Returning a rich, typed result (instead of a bare string) means the UI can show
> confidence, alternatives, and diagnostics without guessing. It's also a stable
> contract other channels/APIs can build on.
> [2] Using an ***enum*** for `status` and `confidence_level` makes the possible values
> explicit and typo-proof, versus passing around loose strings.

---

## The pipeline, step by step

```python
# app/services/faq_service.py — FAQService.answer_question
def answer_question(self, question, top_k=None) -> AnswerResult:
    user_question = (question or "").strip()
    if not user_question:
        return AnswerResult(..., status=ERROR, answer="Please enter a question.")
    try:
        candidates = self._search.search(self._conn, user_question, top_k)
    except IndexNotBuiltError:
        return AnswerResult(..., status=ERROR, answer="The FAQ index has not been built yet.")
    except Exception:
        return AnswerResult(..., status=ERROR, answer="Something went wrong ...")
    if not candidates:
        self._log_unanswered(user_question, None)
        return AnswerResult(..., status=NO_MATCH, answer=FALLBACK_MESSAGE)
    # ... confidence decision (next slide) ...
```

Notice it **never raises** for ordinary problems — empty input, missing index, or a
search error all become an `ERROR` *result*, so the UI has exactly one thing to
render.[1]

> **Footnotes**
> [1] Turning expected failures into structured results (not exceptions) is a
> deliberate choice at a boundary the UI depends on. Truly unexpected bugs are logged
> via `logger.exception` and still return a safe, generic message to the user.

---

## The three confidence bands

```python
# app/services/faq_service.py — FAQService.answer_question (confidence bands)
best = candidates[0]                          # highest score first
if best.score >= settings.similarity_threshold_high:      # ≥ 0.65
    confidence = HIGH
elif best.score >= settings.similarity_threshold_low:     # ≥ 0.45
    confidence = MEDIUM
else:                                                     # < 0.45
    self._log_unanswered(user_question, best.score)
    return AnswerResult(..., status=LOW_CONFIDENCE,
                        answer=FALLBACK_MESSAGE, confidence_level=LOW, ...)
return AnswerResult(..., status=ANSWER_FOUND, answer=best.answer,
                    confidence_level=confidence, ...)
```

| Band | Meaning | User sees |
|------|---------|-----------|
| **High** | strong match | the curated answer |
| **Medium** | plausible match | the answer (UI can caveat it) |
| **Low** | weak match | fallback + suggestions; **logged** for review |

> **Footnotes**
> Both thresholds come from `settings` (Chapter 2), so they're tunable without code
> changes. The order matters: check High first, then Medium, else Low.

---

## Why V1 cannot hallucinate

Look at the Low branch: it returns a **fallback message**, *not* the weak match's
text. The nearest FAQ's answer is only ever shown when it clears the bar.[1]

```text
FALLBACK: "I couldn't find a sufficiently reliable answer to your question.
           Try rephrasing it, or pick one of the suggested related topics."
```

So the worst case is an honest "I don't know," never a confidently wrong answer.
This is the whole safety argument for a retrieval-only V1.[2]

> **Footnotes**
> [1] Contrast with returning `candidates[0].answer` unconditionally — the classic
> bug where a bot answers *everything*, including nonsense, because there's always a
> "nearest" match. The threshold is what prevents this.
> [2] A generation-based bot (LLM) can still be made safe, but it requires extra
> guardrails. Retrieval-only gets safety *by construction*: it can only ever return
> text a human wrote.

---

## Closing the loop: logging unanswered questions

Every Low/No-match question is written to `unanswered_questions`:

```python
# app/services/faq_service.py — FAQService._log_unanswered
def _log_unanswered(self, question, best_score):
    try:
        UnansweredRepository(self._conn).log(question, best_score)
    except sqlite3.Error:
        logger.exception("Failed to log unanswered question.")
```

This is the **feedback loop** that improves coverage over time: an admin reviews the
log and adds the missing FAQs.[1] Note that logging failures never break answering —
the try/except keeps the user's reply flowing.

🛠️ **Try it:** ask something off-topic ("what's the weather?"), then open **Admin →
Unanswered** to see it captured with its best score.

> **Footnotes**
> [1] This is how the system gets better without any machine learning retraining:
> real gaps are surfaced as data, a human fills them, a rebuild makes them
> searchable. Simple, transparent, effective.

---

## Recap & what's next

- **SemanticSearch** produces candidates hydrated from SQLite (stale-safe).
- **FAQService.answer_question** returns one **typed result** and never raises for
  ordinary failures.
- **Three confidence bands**; the Low band returns a **fallback**, so V1 **cannot
  hallucinate**; weak questions are **logged** for review.

**Next:** [Chapter 7 — Channels & Formatting](07-channels-and-formatting.md):
shaping that answer for Chat, WhatsApp, Telegram, and SMS.
