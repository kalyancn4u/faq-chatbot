# Chapter 4 — Embeddings

*The moment text becomes numbers — the heart of semantic search.*

**By the end of this chapter you will be able to:** explain what an embedding is,
why cosine similarity measures meaning, what normalization buys us, and why the
model is loaded once and cached.

File: [`app/embeddings/embedder.py`](../../app/embeddings/embedder.py).

---

## What is an embedding, really?

An ***embedding*** is a fixed-length list of numbers that represents the *meaning*
of a piece of text.[1] A model reads a sentence and outputs, say, 384 numbers.

The key property: **texts with similar meaning get vectors pointing in similar
directions.** So "reset my password" and "I forgot my password" land close
together, even though they share few words.[2]

```text
"reset my password"      → [ 0.02, -0.11, 0.34, ... ]   (384 numbers)
"I forgot my password"   → [ 0.03, -0.09, 0.31, ... ]   ← very close direction
"how long is shipping"   → [-0.20,  0.15, 0.05, ... ]   ← different direction
```

> **Footnotes**
> [1] "Meaning" is learned: the model was trained on huge amounts of text so that
> semantically related sentences end up nearby in this number space. You don't
> program the meaning; the model learned it.
> [2] This number space is often called an ***embedding space*** or *latent space*.
> Directions in it correspond, roughly, to aspects of meaning.

---

## The model: `all-MiniLM-L6-v2`

We use a small, fast, CPU-friendly model from the *sentence-transformers* library:[1]

- outputs **384** numbers per text,
- runs comfortably without a GPU,
- good enough quality for FAQ matching.

It's chosen in **config**, not hard-coded, so switching to a multilingual model is
a one-line change:[2]

```python
self.model_name = model_name or settings.embedding_model_name
```

> **Footnotes**
> [1] ***sentence-transformers*** (a.k.a. SBERT) is a library of models that embed
> whole sentences, not just words. See sbert.net. "MiniLM-L6" is a compact
> 6-layer transformer; "v2" is the version.
> [2] To support other languages, set `EMBEDDING_MODEL_NAME` to a multilingual model
> in `.env`. The rest of the code is unchanged — the payoff of centralized config
> (Chapter 2).

---

## Measuring similarity: cosine

Once two texts are vectors, "how similar are they?" becomes geometry. We use
***cosine similarity*** — the cosine of the angle between the two vectors:[1]

- **1.0** → same direction → same meaning,
- **0.0** → perpendicular → unrelated,
- negative → opposite (rare for this model).

Cosine cares about **direction, not length**, which is what we want: the *topic*
matters, not how long the sentence is.[2]

> **Footnotes**
> [1] Cosine similarity of vectors **a** and **b** is `(a·b) / (|a||b|)`, where `a·b`
> is the dot product. If both vectors have length 1, this simplifies to just `a·b` —
> a fact we exploit next.
> [2] A long question and a short paraphrase can mean the same thing; cosine treats
> them as similar because their *direction* agrees. A distance that cared about
> magnitude would be misled by length.

---

## Normalization: the trick that makes FAISS simple

The embedder returns **L2-normalized** vectors — every vector is scaled to length
1:[1]

```python
vectors = model.encode(
    texts,
    convert_to_numpy=True,
    normalize_embeddings=True,   # ← unit length: dot product == cosine
)
return np.asarray(vectors, dtype=np.float32)
```

Why this matters: for unit vectors, **dot product equals cosine similarity.** So
FAISS's fast inner-product search *is* cosine search — no extra math, no
approximation.[2]

🧠 **Nuance:** this one flag (`normalize_embeddings=True`) is the quiet hinge
between Chapters 4 and 5. Normalize here → use `IndexFlatIP` there → get cosine for
free.

> **Footnotes**
> [1] ***L2 normalization*** divides a vector by its length (its L2 norm) so the
> result has length 1. Geometrically, every point is moved onto the unit sphere;
> only direction remains.
> [2] FAISS offers an inner-product index (`IndexFlatIP`). Inner product of unit
> vectors = cosine. So by normalizing here, we let FAISS compute cosine with its
> fastest primitive. Chapter 5 uses exactly this.

---

## `float32` and shape: speaking FAISS's language

```python
return np.asarray(vectors, dtype=np.float32)   # shape (n, 384)
```

- FAISS expects **`float32`** arrays; the embedder always returns that dtype.[1]
- The shape is always 2-D `(n_texts, dimension)`, even for one query
  (`encode_one` returns `(1, 384)`), so it can go straight into FAISS without
  reshaping.[2]

⚠️ **Pitfall:** passing `float64` (NumPy's default) to FAISS errors or silently
copies. Fixing the dtype *at the source* means no caller has to remember.

> **Footnotes**
> [1] ***dtype*** = the numeric type of array elements. `float32` uses half the
> memory of `float64` and is what FAISS is built around. NumPy defaults to
> `float64`, so we convert explicitly.
> [2] Keeping a single query 2-D (`(1, 384)`) avoids a whole category of
> "expected 2-D, got 1-D" bugs at the FAISS boundary.

---

## Loading once, caching forever

Loading the model takes a few seconds. Doing it per request would make the app
crawl. So it's cached:

```python
@lru_cache(maxsize=2)
def _load_model(model_name: str):
    from sentence_transformers import SentenceTransformer   # imported lazily
    return SentenceTransformer(model_name, device="cpu")
```

- `@lru_cache` returns the **same** loaded model on every call with the same
  name.[1]
- The heavy import is **lazy** (inside the function), so simply importing this
  module doesn't pull in PyTorch.[2]

> **Footnotes**
> [1] ***`lru_cache`*** memoizes a function: same arguments → cached result. Here the
> "result" is the loaded model object, so it loads at most once per model name per
> process. In the Streamlit UI a second layer (`st.cache_resource`, Chapter 8)
> keeps it alive across reruns.
> [2] ***Lazy import*** = import inside the function, not at the top of the file, so
> the cost is paid only if/when the function actually runs. This keeps tests and
> tools that don't embed fast to import.

---

## Offline mode (a real-world wrinkle)

On networks that intercept TLS to huggingface.co, the model's *update check* can
hang. Once the model is cached locally, `HF_OFFLINE=1` skips the network entirely:[1]

```python
if settings.hf_offline:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")
```

🛠️ **Try it:** in a Python shell (with the venv active), run
`from app.embeddings.embedder import get_embedder; e = get_embedder();
print(e.encode(["reset password","forgot password"]) @ e.encode(["reset password"]).T)`
— the two paraphrases score high; an unrelated sentence scores low.

> **Footnotes**
> [1] This is set in `settings.py` so it takes effect *before* the Hugging Face
> libraries are imported (they read these variables at import time). A small ordering
> detail with a big effect on startup speed — see the project README's
> troubleshooting section.

---

## Recap & what's next

- An **embedding** turns text into a direction in number space; **cosine**
  measures how aligned two meanings are.
- **Normalizing** to unit length makes FAISS's inner product equal cosine.
- The model returns **`float32` 2-D** arrays and is **loaded once** and cached; the
  heavy import is **lazy**.

**Next:** [Chapter 5 — FAISS & the Index](05-faiss-and-the-index.md): storing those
vectors so we can find the nearest ones instantly — and keeping the index perfectly
in sync with SQLite.
