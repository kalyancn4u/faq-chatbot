# Chapter 9 — Testing & Quality

*How we prove the system works — and test ML code without brittleness.*

**By the end of this chapter you will be able to:** explain how the test suite is
organized, use pytest fixtures, understand why some tests load the real model, and
write robust assertions for semantic search.

Folder: [`tests/`](../../tests/).

---

## Why test at all? (especially here)

Tests are executable proof that the code does what you claim — and a safety net that
lets you change code confidently.[1] In *this* app they matter doubly, because the
pieces are interdependent: an off-by-one in the id map, or a wrong dtype, would
silently return the wrong answer.

The suite (44+ tests) covers every layer: database, embeddings, index consistency,
retrieval, confidence, formatting, and the pure UI helpers.[2]

> **Footnotes**
> [1] This is ***regression testing***: once a behavior is covered, a future edit that
> breaks it fails a test instead of shipping a bug. Run them with `pytest`.
> [2] Coverage is chosen by *risk*, not vanity: the consistency invariant and the
> confidence logic get the most attention because they're where a silent wrong answer
> could hide.

---

## Fixtures: fast, isolated test setup

***Fixtures*** are reusable setup that pytest injects into tests by name.[1] The key
ones live in [`tests/conftest.py`](../../tests/conftest.py):

```python
@pytest.fixture
def conn(tmp_path):                    # a fresh SQLite file per test
    connection = connect(tmp_path / "test.db")
    initialize_database(connection)
    yield connection
    connection.close()

@pytest.fixture
def seeded_conn(conn):                 # same, pre-loaded with a few FAQs
    for q, a, c in SEED_FAQS: FAQRepository(conn).add(q, a, category=c)
    conn.commit()
    return conn
```

Each test gets its **own temp database** — no shared state, no order dependence, and
nothing touches your real `data/` files.[2]

> **Footnotes**
> [1] A ***fixture*** is requested by putting its name in a test's parameters (e.g.
> `def test_x(seeded_conn):`). pytest builds it, hands it over, and tears it down
> after. Fixtures can depend on other fixtures (`seeded_conn` uses `conn`).
> [2] `tmp_path` is a pytest built-in giving each test a unique temporary directory.
> Isolation like this is why the suite is reliable and re-runnable.

---

## Loading the real model — once

Some tests need genuine embeddings (to check that paraphrases actually match). We
load the real model, but only **once per test session**:

```python
@pytest.fixture(scope="session")
def embedder() -> Embedder:
    return Embedder()                  # loaded a single time for all tests
```

- `scope="session"` means the model is built once and shared by every test that asks
  for it — the slow part is paid once.[1]
- The FAISS index for tests is written under `tmp_path`, never the real `data/indexes`.

> **Footnotes**
> [1] ***Fixture scope*** controls lifetime: `function` (default) rebuilds per test;
> `session` builds once for the whole run. Loading a transformer per test would make
> the suite painfully slow — session scope fixes that without sacrificing isolation of
> the *data* (which stays per-test).

---

## Testing the invariant and the mapping

The riskiest logic gets the most direct tests:

```python
def test_rebuild_creates_consistent_artifacts(index_manager, seeded_conn):
    result = index_manager.rebuild(seeded_conn)
    status = index_manager.status(seeded_conn)
    assert status.indexed_vectors == status.mapped_ids == status.active_faqs

def test_search_maps_positions_to_faq_ids(built_index, seeded_conn):
    hits = built_index.search("I can't remember my password", top_k=3)
    faq = FAQRepository(seeded_conn).get(hits[0][0])
    assert "password" in faq.question.lower()
```

The first asserts the **consistency invariant** (Chapter 5) directly; the second
proves a FAISS position round-trips to the **right** FAQ.[1]

> **Footnotes**
> [1] There are also tests for the *unhappy paths*: rebuilding with no active FAQs
> raises, a search with no index raises `IndexNotBuiltError`, and a corrupted id map
> is detected on load. Testing failure modes is as important as testing success.

---

## Testing semantics without brittleness

Embedding scores are floating-point and model-dependent. Asserting
`score == 0.9203...` would be **brittle** — a library update could change the last
digits and break the test for no real reason.[1] Instead we assert **relationships**:

```python
def test_paraphrases_are_more_similar_than_unrelated(embedder):
    v = embedder.encode(["How do I reset my password?",
                         "I forgot my password.",
                         "How long does shipping take?"])
    assert float(v[0] @ v[1]) > float(v[0] @ v[2])   # paraphrase closer than unrelated
```

We check *"paraphrase scores higher than unrelated"* and *"an off-topic query scores
below the threshold"* — properties that stay true even if exact numbers drift.[2]

> **Footnotes**
> [1] ***Brittle test*** = one that fails on harmless changes. Pinning exact floats
> couples your test to a model's internals. When you must compare floats, use a
> tolerance (`pytest.approx`), as the feedback-score tests do.
> [2] This is ***property-based thinking***: assert the invariant that must hold
> ("closer than"), not a specific value. It's the right way to test ML outputs.

---

## Testing pure functions is easy — so we made functions pure

The formatter and the HTML builders are **pure functions** (input → output, no side
effects), which makes them trivial to test without a browser or a model:[1]

```python
def test_telegram_escapes_reserved_characters():
    out = format_reply(_answer("Go to Settings > Billing (30-day)."), Channel.TELEGRAM)
    assert r"\>" in out.text and r"\-" in out.text and r"\." in out.text

def test_candidates_table_is_responsive_and_wrapping():
    html = build_candidates_table_html([{"faq_id": 1, "question": "...", "score": 0.91}])
    assert "table-layout:fixed" in html and "word-break:break-word" in html
```

🧠 **Nuance:** the fact that these were *easy* to test is a design win. `format_reply`
and `build_candidates_table_html` were written to take data and return a string —
so the tests need no Streamlit runtime at all.[2]

> **Footnotes**
> [1] A ***pure function*** always returns the same output for the same input and
> changes nothing else. Pure functions are the easiest code to test, cache, and
> reason about — worth extracting wherever practical.
> [2] "Design for testability" isn't extra work; it usually *is* good design. Hard-to-
> test code is often a hint that responsibilities are tangled.

---

## Running and reading the suite

```bash
pytest            # run everything
pytest -q         # quiet summary
pytest tests/test_formatting.py -q     # one file
```

A green run (`44 passed`) is the contract that the whole pipeline — from SQL to
channel formatting — still behaves. Make it a habit to run it after every change.[1]

🛠️ **Try it:** open `tests/test_services.py`, read
`test_low_confidence_returns_fallback_and_logs`, and trace how it asserts *both* the
fallback message *and* that the question was logged. That single test guards Design
Law #2.

> **Footnotes**
> [1] In a team setting this runs automatically in ***CI*** (Continuous Integration)
> on every push, blocking merges that break tests. Locally, `pytest` before committing
> is the same discipline at human scale.

---

## Recap & what's next

- Tests are **risk-driven** and cover every layer.
- **Fixtures** give each test an isolated temp DB; the **real model** loads once per
  session.
- Semantic tests assert **relationships, not exact floats**; pure functions make
  formatting/HTML **easy to test**.

**Next:** [Chapter 10 — Mastery: End-to-End & Exercises](10-mastery-end-to-end.md):
one query traced through every layer, extension projects, and a self-check.
