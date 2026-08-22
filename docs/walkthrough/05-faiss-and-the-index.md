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
> [1] ***FAISS*** = Facebook AI Similarity Search, a C++/Python library for fast
> similarity search over dense vectors. See faiss.ai. We use `faiss-cpu` (no GPU).
> [2] This is the crux of Design Law #1: FAISS finds *where*; SQLite holds *what*.

---

## Choosing the simplest correct index

```python
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
> [1] "Flat" means the vectors are stored plainly and scanned exhaustively — a
> brute-force but exact search. "IP" = inner (dot) product.
> [2] Scores come back in roughly 0–1 for this model. No conversion needed — the
> confidence thresholds (Chapter 6) compare directly to these.
> [3] ***IVF/HNSW*** are approximate methods that trade a little accuracy for speed
> at millions of vectors. Using them now would add tuning knobs and subtle recall
> loss for zero benefit — a textbook case of avoiding premature optimization. The
> `build_index` interface is the seam where they'd slot in later.

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
faq_ids = [f.id for f in faqs]         # order matches the embeddings
questions = [f.question for f in faqs]
embeddings = self._embedder.encode(questions)
index = faiss_index.build_index(embeddings)
```

A search result at position `p` maps to `faq_ids[p]`, which we then look up in
SQLite.[1]

> **Footnotes**
> [1] Because embeddings and `faq_ids` are built from the same ordered list, position
> `p` in the index and index `p` in `faq_ids` always refer to the same FAQ. The
> id map is stored next to the index as JSON, together with the model name and
> dimension (used for staleness checks).

---

## The consistency invariant

After building, the code **validates** before publishing anything:

```python
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
> [1] An ***invariant*** is a condition that must always hold. Checking it turns a
> silent corruption into a loud, catchable error at the safest moment (before the
> index goes live).
> [2] "Fail loud, never silent" again. A wrong-but-quiet index would map a query to
> the wrong answer — far worse than an obvious error the admin can fix by rebuilding.

---

## Atomic rebuild: never leave a half-written index

If the app crashed mid-write, you could end up with a new index but an old id map —
inconsistent. To prevent this, we write to **temp files**, then **atomically
replace**:[1]

```python
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
> [1] ***Atomic*** = happens completely or not at all, with no observable in-between
> state. `os.replace` is atomic within one filesystem.
> [2] The load path also re-validates (`indexed == mapped`) so even a partially
> written pair is caught rather than trusted.

---

## Staleness: knowing when to rebuild

The index is a derived artifact, so it can fall out of date. `is_stale` detects
this by comparing the map to the current world:[1]

```python
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
> [1] Comparing *sorted id sets* catches additions, deletions, and de/reactivations —
> anything that changes which FAQs should be searchable.
> [2] For V1 we always do a **full rebuild** on change. For a small/medium set this is
> simple and correct; incremental add/remove bookkeeping is easy to get subtly wrong
> and isn't worth it yet.

---

## Searching, end to end (within the index)

```python
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
> [1] Separating "no index" (a recoverable state → rebuild) from "bad query" keeps
> error handling honest and user-friendly.
> [2] FAISS pads results to `k` with position `-1` and score `-inf` when the index
> holds fewer than `k` vectors. Filtering `-1` avoids indexing errors.

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
