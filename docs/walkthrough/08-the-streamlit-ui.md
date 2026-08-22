# Chapter 8 — The Streamlit UI

*How the pages are built, and the rerun model that makes Streamlit tick.*

**By the end of this chapter you will be able to:** explain Streamlit's rerun
model, use `cache_resource` and `session_state` correctly, and understand the safe,
responsive HTML the app renders.

Files: [`main.py`](../../app/main.py), [`components.py`](../../app/ui/components.py),
[`chat.py`](../../app/ui/chat.py), [`admin.py`](../../app/ui/admin.py).

---

## The one idea you must grok: reruns

***Streamlit*** builds a web UI from a plain Python script. The mental model that
surprises everyone at first:[1]

> **Every interaction re-runs the entire script from top to bottom.**

Click a button, type in a box, move a slider → Streamlit executes `main.py` again,
start to finish, and redraws the page from the result.[2]

This is why we need two tools: something to **remember** data across reruns
(`session_state`) and something to **avoid re-doing expensive work** each rerun
(`cache_resource`).

> **Footnotes**
>
> - **[1]** ***Streamlit*** turns Python into a web app with no HTML/JS required — `st.write`, `st.button`, `st.chat_input`, etc. See docs.streamlit.io.
> - **[2]** It feels wasteful but is what makes Streamlit simple: your script always describes the *current* screen as a function of the *current* state. No callbacks, no manual DOM updates.

---

## `cache_resource`: load heavy things once

The embedding model and the FAISS index must **not** reload on every rerun. We cache
them:

```python
# app/ui/components.py
@st.cache_resource(show_spinner=False)
def get_index_manager() -> IndexManager:
    return IndexManager()

@st.cache_resource(show_spinner="Preparing the FAQ database and index...")
def bootstrap() -> bool:
    ensure_directories()
    with get_connection() as conn:
        initialize_database(conn)
        if FAQRepository(conn).count_active() and get_index_manager().is_stale(conn):
            get_index_manager().rebuild(conn)
    return True
```

`cache_resource` returns the **same object** on every rerun, shared across the
session.[1] So the model loads once, the index is built once, and the chat stays
instant.[2]

> **Footnotes**
>
> - **[1]** ***`st.cache_resource`*** is for global, non-serializable resources (models, DB connections, clients). Its sibling `st.cache_data` is for *data* results (it copies them). Using the right one matters: you want *one shared* IndexManager, not a copy per call.
> - **[2]** `bootstrap()` also self-heals: on first launch it creates the schema and builds the index if needed, so a new user gets a working chat with no manual step.

---

## `session_state`: remember across reruns

The chat history must survive reruns (otherwise every keystroke would erase the
conversation):

```python
# app/ui/chat.py — render_chat_page
st.session_state.setdefault("history", [])          # persists across reruns
...
st.session_state.history.append({"result": result, "feedback": None})
st.rerun()                                           # redraw with the new turn
```

`session_state` is a per-user dictionary that Streamlit keeps between reruns.[1] We
store the **raw `AnswerResult`** (not pre-formatted text), which is why switching the
reply channel reformats the *whole* conversation instantly.[2]

> **Footnotes**
>
> - **[1]** ***`st.session_state`*** = a dict-like store scoped to one browser session. `setdefault` initializes it once. `st.rerun()` triggers an immediate re-execution so new state is reflected right away.
> - **[2]** Storing the *result* and formatting at *display* time (Chapter 7) is the key design choice behind instant channel switching — a small decision with a big UX payoff.

---

## Composition: main → pages → components

The UI is layered like the rest of the app:

- [`main.py`](../../app/main.py) — sets up the page, the sidebar (page selector,
  **Reply format**, **Developer mode**), and dispatches to a page.
- [`chat.py`](../../app/ui/chat.py) / [`admin.py`](../../app/ui/admin.py) — the two
  pages.
- [`components.py`](../../app/ui/components.py) — shared widgets (confidence badge,
  the channel preview box, the diagnostics table) and the cached resources.

Each page **calls services** (Chapter 6/7); it contains no SQL and no FAISS code.[1]

> **Footnotes**
>
> - **[1]** This keeps the UI thin and the logic testable. A page's job is to gather input, call a service, and render the result — nothing more. You could put a different UI (an API, a CLI) on the same services unchanged.

---

## The chat turn: rendering one exchange

```python
# app/ui/chat.py
def _render_turn(index, entry, channel, dev_mode):
    with st.chat_message("user"):
        st.write(entry["result"].user_question)
    with st.chat_message("assistant"):
        if channel is Channel.CHAT:
            _render_chat_reply(result, dev_mode)      # rich markdown + badge
        else:
            _render_channel_preview(result, channel)  # exact as-sent preview
        _render_feedback(index, entry, result)        # 👍/👎, stored to SQLite
        if dev_mode:
            _render_diagnostics(result)               # scores + candidates table
```

Feedback buttons write to the `feedback` table via `FeedbackService`; each turn is
keyed by its index so clicks don't collide.[1]

> **Footnotes**
>
> - **[1]** Widget ***keys*** (e.g. `key=f"fb_yes_{index}"`) must be unique — Streamlit uses them to track widget state across reruns. Reusing a key across turns would make two buttons share state. Indexing by turn number keeps them distinct.

---

## Safe, responsive HTML rendering

Some previews need real HTML (a wrapping monospace box, a responsive table).
Streamlit allows it, but raw content must be made safe and literal:[1]

```python
# app/ui/components.py
def escape_literal(text):
    out = html.escape(str(text), quote=False)          # neutralize < > &
    for char, entity in _MD_NEUTRALIZE.items():         # * _ ` ~ [ ] \  -> entities
        out = out.replace(char, entity)
    return out
```

Two problems this solves at once:

- **Security:** escaping `< > &` means content can't inject markup.[2]
- **Fidelity:** entity-encoding `*`, `\`, etc. stops Streamlit's markdown from
  *interpreting* them — so `*Confidence:*` and Telegram's `\.` show **literally**,
  exactly as the channel sends them.

The preview box uses `white-space: pre-wrap` + `overflow-wrap`, and the diagnostics
table uses `table-layout: fixed`, so both **wrap and stay responsive** as the window
resizes.[3]

> **Footnotes**
>
> - **[1]** `st.markdown(..., unsafe_allow_html=True)` renders HTML. "Unsafe" is a real warning: never pass unescaped user content to it. Here every dynamic value goes through `escape_literal` first.
> - **[2]** ***HTML-escaping*** converts `<` → `&lt;` etc. so text can't become tags — the basic defense against cross-site scripting (XSS).
> - **[3]** These CSS choices (`pre-wrap`, `overflow-wrap:anywhere`, `table-layout:fixed`) are what make long replies and long questions flow to the window width instead of overflowing sideways. Verified with unit tests on the pure HTML builders.

---

## Admin page: safe by default

The admin page (FAQ CRUD, CSV import/export, index rebuild, reviews) follows one
rule: **make destructive actions safe.**[1]

- Deleting requires ticking a **confirm** checkbox first.
- **Deactivate** is offered as the safer default (soft-delete, Chapter 3).
- CSV imports are **validated before** writing.
- After changes, the UI reminds you to **rebuild the index**.

🛠️ **Try it:** in Admin → FAQs, add an FAQ, then go to Admin → Index and click
*Rebuild index now*. Watch the status metrics update — that's the consistency
invariant (Chapter 5) shown live.

> **Footnotes**
>
> - **[1]** Guardrails on irreversible actions are a usability *and* safety feature. The admin isn't expected to know ML; the workflow is simply "edit FAQs → rebuild → they're searchable."

---

## Recap & what's next

- Streamlit **re-runs the whole script** on every interaction.
- **`cache_resource`** loads heavy things once; **`session_state`** remembers across
  reruns.
- The UI is **thin** (calls services), stores **raw results** (instant reformatting),
  and renders **safe, responsive HTML**.

**Next:** [Chapter 9 — Testing & Quality](09-testing-and-quality.md): how we prove
all of this works, and test ML code without brittleness.
