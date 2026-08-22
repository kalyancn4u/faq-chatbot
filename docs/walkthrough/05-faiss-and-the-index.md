# Chapter 5 — FAISS & the Index

*Finding the nearest vectors fast, and keeping the index perfectly in sync with
the source of truth.*

**By the end of this chapter you will be able to:** explain what a vector index is,
why we chose an exact `IndexFlatIP`, how the FAISS↔SQLite id map works, and how the
rebuild stays atomic and consistent.

Files: [`faiss_index.py`](../../app/retrieval/faiss_index.py),
[`index_manager.py`](../../app/retrieval/index_manager.py).

---

## The job: nearest-vector search

We have one query vector and (say) 30 stored FAQ vectors. We want the closest few.
You *could* compare the query to every stored vector by hand — and for 30 that's
fine. ***FAISS*** does exactly this, but efficiently and correctly, and scales to
millions.[1]

FAISS knows only about **vectors and their positions** (row 0, row 1, …). It does
**not** know about FAQ ids, questions, or answers. Remember that — the id map
(coming up) exists precisely to bridge this gap.[2]

> **Footnotes**
>
> - **[1]** ***FAISS*** = Facebook AI Similarity Search, a C++/Python library for fast similarity search over dense vectors. See faiss.ai. We use `faiss-cpu` (no GPU).
> - **[2]** This is the crux of Design Law #1: FAISS finds *where*; SQLite holds *what*.

---

## Choosing the simplest correct index

```python
# app/retrieval/faiss_index.py
def build_index(embeddings):
    index = faiss.IndexFlatIP(embeddings.shape[1])   # inner product, exact
    index.add(vectors)
    return index
```

- ***`IndexFlatIP`*** = a "flat" index that compares the query against **every**
  vector using **inner product** — no approximation.[1]
- Because our vectors are unit-length (Chapter 4), inner product **is** cosine
  similarity. So this index returns cosine scores directly.[2]

Why exact/flat? For a small-to-medium FAQ set it's fast, has **nothing to tune**,
and is always correct. Approximate indexes (IVF, HNSW) only pay off at large
scale.[3]

> **Footnotes**
>
> - **[1]** "Flat" means the vectors are stored plainly and scanned exhaustively — a brute-force but exact search. "IP" = inner (dot) product.
> - **[2]** Scores come back in roughly 0–1 for this model. No conversion needed — the confidence thresholds (Chapter 6) compare directly to these.
> - **[3]** ***IVF/HNSW*** are approximate methods that trade a little accuracy for speed at millions of vectors. Using them now would add tuning knobs and subtle recall loss for zero benefit — a textbook case of avoiding premature optimization. The `build_index` interface is the seam where they'd slot in later.

---

## The id map: FAISS position ↔ SQLite id

FAISS returns positions (`0, 1, 2, …`). We must translate those back to real FAQ
ids. The trick is to keep a **parallel list**:

```text
FAISS row:   0        1        2        3
faq_ids:  [ 12,      7,       31,      4 ]     ← faq_ids[position] = SQLite id
```

We build the vectors and this list **in the same order**, then persist both:

```python
# app/retrieval/index_manager.py — IndexManager.rebuild
faq_ids = [f.id for f in faqs]         # order matches the embeddings
questions = [f.question for f in faqs]
embeddings = self._embedder.encode(questions)
index = faiss_index.build_index(embeddings)
```

A search result at position `p` maps to `faq_ids[p]`, which we then look up in
SQLite.[1]

> **Footnotes**
>
> - **[1]** Because embeddings and `faq_ids` are built from the same ordered list, position `p` in the index and index `p` in `faq_ids` always refer to the same FAQ. The id map is stored next to the index as JSON, together with the model name and dimension (used for staleness checks).

---

## The consistency invariant

After building, the code **validates** before publishing anything:

```python
# app/retrieval/index_manager.py
def _validate(indexed, mapped, expected_active):
    if not (indexed == mapped == expected_active):
        raise IndexConsistencyError(...)
```

The invariant, in words:[1]

```text
number of vectors in the index
    == number of ids in the map
    == number of active FAQs in SQLite
```

If these three ever disagree, the index is broken and the code **refuses to use
it** rather than returning wrong answers.[2]

> **Footnotes**
>
> - **[1]** An ***invariant*** is a condition that must always hold. Checking it turns a silent corruption into a loud, catchable error at the safest moment (before the index goes live).
> - **[2]** "Fail loud, never silent" again. A wrong-but-quiet index would map a query to the wrong answer — far worse than an obvious error the admin can fix by rebuilding.

---

## Atomic rebuild: never leave a half-written index

If the app crashed mid-write, you could end up with a new index but an old id map —
inconsistent. To prevent this, we write to **temp files**, then **atomically
replace**:[1]

```python
# app/retrieval/index_manager.py — IndexManager._atomic_write
faiss_index.save_index(index, tmp_index)
tmp_map.write_text(json.dumps(payload))
os.replace(tmp_index, self._index_path)     # atomic on the same filesystem
os.replace(tmp_map, self._id_map_path)
```

`os.replace` swaps the file in one indivisible step, so readers see either the old
pair or the new pair — never a mix.[2]

⚠️ **Pitfall:** writing directly to the live files means a crash leaves a corrupt
index that *looks* present. Temp-then-replace is the standard safe-write recipe.

> **Footnotes**
>
> - **[1]** ***Atomic*** = happens completely or not at all, with no observable in-between state. `os.replace` is atomic within one filesystem.
> - **[2]** The load path also re-validates (`indexed == mapped`) so even a partially written pair is caught rather than trusted.

---

## Staleness: knowing when to rebuild

The index is a derived artifact, so it can fall out of date. `is_stale` detects
this by comparing the map to the current world:[1]

```python
# app/retrieval/index_manager.py
def is_stale(self, conn) -> bool:
    if not self.exists(): return True
    if payload["model"] != self._embedder.model_name: return True   # model changed
    mapped_ids = sorted(payload["faq_ids"])
    active_ids = sorted(f.id for f in FAQRepository(conn).list_active())
    return mapped_ids != active_ids                                  # FAQ set changed
```

So the index is stale if it's missing, was built with a **different model**, or no
longer matches the **set of active FAQs**. The UI uses this to prompt a rebuild, and
to build automatically on first launch.[2]

> **Footnotes**
>
> - **[1]** Comparing *sorted id sets* catches additions, deletions, and de/reactivations — anything that changes which FAQs should be searchable.
> - **[2]** For V1 we always do a **full rebuild** on change. For a small/medium set this is simple and correct; incremental add/remove bookkeeping is easy to get subtly wrong and isn't worth it yet.

---

## Searching, end to end (within the index)

```python
# app/retrieval/index_manager.py — IndexManager.search
def search(self, query, top_k=None):
    self._ensure_loaded()                       # load from disk if needed
    query_vec = self._embedder.encode_one(query)
    scores, positions = faiss_index.search(self._index, query_vec, k)
    return [(self._faq_ids[int(p)], float(s))   # position → faq_id, with score
            for p, s in zip(positions[0], scores[0]) if p != -1]
```

- If no index exists yet, it raises a clear `IndexNotBuiltError` (the service turns
  this into a friendly message, Chapter 6).[1]
- A position of `-1` means "empty slot" (fewer vectors than `k`) and is skipped.[2]

🛠️ **Try it:** run `python scripts/rebuild_index.py --status` to see the invariant
live: indexed vectors, mapped ids, and active FAQ count should all match.

> **Footnotes**
>
> - **[1]** Separating "no index" (a recoverable state → rebuild) from "bad query" keeps error handling honest and user-friendly.
> - **[2]** FAISS pads results to `k` with position `-1` and score `-inf` when the index holds fewer than `k` vectors. Filtering `-1` avoids indexing errors.

---

## Recap & what's next

- FAISS finds nearest vectors; we use an **exact `IndexFlatIP`** so inner product =
  cosine.
- An **id map** bridges FAISS positions to SQLite ids; a **consistency invariant**
  guards it.
- Rebuilds are **atomic**; **staleness** is detected by comparing model + active-id
  set.

**Next:** [Chapter 6 — Retrieval & Confidence](06-retrieval-and-confidence.md):
turning raw matches into a trustworthy answer — or an honest fallback.

📎 **Bonus:** the appendix below answers a question every reader eventually asks —
*"why not just use a vector database like Chroma?"*

---

# Appendix A — "Why not Chroma?" (SQLite + FAISS vs a vector database)

*A common, reasonable question — and the answer teaches you how these tools really
differ.*

**By the end of this appendix you will be able to:** explain why FAISS and Chroma
are different *kinds* of tool, why SQLite + FAISS is the right choice for Version 1,
and exactly when a vector database would earn its place.

---

## The category confusion to clear up first

The question "shouldn't we use Chroma?" quietly assumes FAISS and Chroma are the
same kind of thing. They are not:[1]

- **FAISS is a *library* — an index.** It knows only vectors and positions; it finds
  nearest neighbours fast. It does **not** store your text or metadata, has no CRUD,
  and cannot filter by attributes.[2]
- **Chroma is a *database*.** It bundles a vector index *plus* persistence, document
  and metadata storage, collections, metadata filtering (`where` clauses), and
  add/upsert/delete — often behind a client/server API, using **approximate** (HNSW)
  search underneath.[3]

So the real comparison is not "FAISS vs Chroma." It is **"SQLite + FAISS" (two
focused tools) vs "Chroma" (one bundled tool)**.

> **Footnotes**
>
> - **[1]** Getting the *category* right is half of understanding any tooling decision. Comparing a library to a database leads to confused conclusions.
> - **[2]** Because FAISS can't filter, this project filters a different way: it builds the index only from *active* FAQs and re-checks each hit against SQLite (Chapter 6).
> - **[3]** ***HNSW*** (Hierarchical Navigable Small World) is a graph-based *approximate* nearest-neighbour method — fast at huge scale, but it can miss the true nearest vector. Contrast our exact `IndexFlatIP`, which never does.

---

## The key realization

We already have **both halves** of what Chroma offers:

```text
Chroma  =  vector index      +  document/metadata database
           └── FAISS does this   └── SQLite does this
```

Chroma would be a **substitute** for a combination we built deliberately — not a
missing capability we lack.[1] And building it ourselves from two transparent tools
is what makes the two Design Laws *visible*: SQLite is truth, FAISS is derived, and
the id-map + consistency invariant tie them together.[2]

> **Footnotes**
>
> - **[1]** This reframing is the whole answer in one line: you can't "need" a tool that replaces something you already have working, unless it does the job better *for your situation*. The next slide checks whether it would.
> - **[2]** A bundled store hides that boundary. For a project whose goal is *learning*, hiding the most important relationship in the system is a real cost.

---

## Why SQLite + FAISS is right for Version 1

Five concrete reasons, each an application of *Simple → Correct → …*:[1]

1. **Scale doesn't demand it.** With tens-to-thousands of FAQs, exact `IndexFlatIP`
   returns in well under a millisecond — *more* accurate than approximate search,
   with nothing to tune. Chroma's strengths (approximate ANN, sharding) go unused.
2. **Transparency.** You can *see* the source-of-truth vs derived-index split; a
   bundled DB obscures it.
3. **Truly local, fewer parts.** No extra dependency or service; one `.db` file and
   one `.faiss` file, CPU-only.
4. **SQLite owns the answers.** Authoritative text, constraints, feedback, and logs
   live in SQL — not tempted into the vector store.
5. **No document ingestion yet.** There's no PDF chunking or RAG in V1, so Chroma's
   document features would sit idle.[2]

> **Footnotes**
>
> - **[1]** Notice none of these is "Chroma is bad." It's a fine tool — just aimed at problems V1 doesn't have. Choosing tools to your *actual* constraints is the skill.
> - **[2]** ***RAG*** (Retrieval-Augmented Generation) chunks documents, retrieves passages, and has an LLM write a grounded answer. That's a natural later version — and the point where a vector DB starts to pull its weight.

---

## When a vector database *would* earn its place

Being honest about the trade-off — you'd want Chroma (or similar) when:[1]

- the corpus grows to **hundreds of thousands / millions** of vectors (approximate
  search becomes worth it);
- you ingest **documents with chunking** and do **RAG**;
- you need **metadata filtering combined with vector search at query time** (e.g.
  "nearest *where* `category = billing`") — FAISS can't do this natively;
- you want **incremental upserts/deletes** rather than full index rebuilds;
- you want embeddings + metadata **persisted and managed together** for you.

None of these are true for V1 — which is why Chroma is a *deferred* choice, not a
rejected one.[2]

> **Footnotes**
>
> - **[1]** A senior engineer states the conditions under which they'd change their mind. If you can't name what would flip the decision, you haven't finished thinking.
> - **[2]** "Deferred, not rejected" matters: the architecture is *designed* to adopt it later (next slide), so choosing simplicity now costs nothing in the future.

---

## Side by side, and the swap-in path

| | **SQLite + FAISS** (chosen) | **Chroma** |
|---|---|---|
| Type | database + index (two focused tools) | bundled vector database |
| Search | **exact** (FlatIP) — perfect recall | approximate (HNSW) |
| Best at | small/medium, transparent, local | large corpora, RAG, filtered queries |
| Metadata filtering | via SQLite | native, at query time |
| Extra service / deps | none | more |

Swapping later is a **one-seam change**: reimplement [`SemanticSearch`](../../app/retrieval/search.py)
against Chroma; the confidence logic, channels, and UI depend on that interface, not
on FAISS, so they don't change.[1]

🧠 **In one sentence:** *we don't need Chroma because we already have its two jobs —
SQLite (truth + metadata) and FAISS (fast exact vector search) — in a form that is
simpler, exact at this scale, fully local, and transparent enough to learn from.*

> **Footnotes**
>
> - **[1]** This is the payoff of the layered design from Chapters 5–6: a big infrastructure swap is contained behind one interface. If swapping the vector store forced changes across the UI and services, that would signal a leaky abstraction — it doesn't here.

---

## Appendix recap

- FAISS is an **index (library)**; Chroma is a **database**. The honest comparison is
  **SQLite + FAISS vs Chroma**.
- We already have both of Chroma's jobs, more transparently — so for V1's scale and
  goals, Chroma would add opacity and dependencies without adding capability.
- It becomes worth adopting at **large scale, for document RAG, or query-time
  metadata filtering** — and the retrieval seam is ready for that swap.

**Back to:** [Chapter 5](#chapter-5--faiss--the-index) · **Continue:**
[Chapter 6 — Retrieval & Confidence](06-retrieval-and-confidence.md).
