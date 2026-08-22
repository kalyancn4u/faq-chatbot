# Chapter 2 — Configuration & Logging

*Where every setting lives, and why that matters more than it looks.*

**By the end of this chapter you will be able to:** explain why configuration is
centralized, read a frozen dataclass, override any setting from the environment,
and use the project's logging helper.

Files: [`app/config/settings.py`](../../app/config/settings.py),
[`app/config/logging_config.py`](../../app/config/logging_config.py).

---

## The problem: scattered "magic numbers"

Imagine `top_k = 5` and `threshold = 0.65` copied into ten files. Change your mind,
and you must find and edit all ten — and you *will* miss one.[1]

The fix is a single **source of configuration**: one module that every other module
imports. Change a value once, everywhere sees it.

🧠 **Nuance:** this is the difference between a value that is *used* in many places
and a value that is *defined* in many places. The first is fine; the second is a bug
waiting to happen.

> **Footnotes**
> [1] These stray constants are called ***magic numbers*** — unexplained literals
> buried in code. Centralizing them also gives each a name and a docstring, so the
> *meaning* travels with the value.

---

## One frozen object, imported everywhere

```python
@dataclass(frozen=True)
class Settings:
    embedding_model_name: str
    top_k: int
    similarity_threshold_high: float
    similarity_threshold_low: float
    db_path: Path
    index_dir: Path
    log_level: str
    hf_offline: bool

settings: Settings = _build_settings()   # one shared instance
```

Other modules do exactly one thing:

```python
from app.config.settings import settings
k = settings.top_k
```

- `@dataclass` auto-writes the boilerplate (init, repr).[1]
- `frozen=True` makes it **immutable** — no code can accidentally change a setting
  mid-run, so behavior can't drift.[2]

> **Footnotes**
> [1] A ***dataclass*** is a Python class whose fields you declare by name and type;
> the decorator generates the plumbing. See the stdlib `dataclasses` docs.
> [2] ***Immutable*** = cannot be changed after creation. Attempting `settings.top_k = 9`
> raises an error. Immutability is a cheap way to remove a whole class of bugs
> ("who changed this and when?").

---

## Sensible defaults, overridable by environment

Each value is read from an environment variable, falling back to a default:

```python
top_k = _get_int("TOP_K", 5)
db_path = _resolve(_get_str("DB_PATH", "data/database/faq.db"))
hf_offline = _get_bool("HF_OFFLINE", False)
```

- **No setup needed** to run locally (defaults just work).
- **Deployment-specific** values come from the environment, not code edits.[1]

Values load from a local `.env` file if present, via `python-dotenv`:[2]

```python
load_dotenv(PROJECT_ROOT / ".env", override=False)
```

`override=False` means a real environment variable always beats the `.env` file —
the standard precedence.[3]

> **Footnotes**
> [1] This is a core idea of the ***twelve-factor app***: keep configuration in the
> environment, separate from code, so the same code runs unchanged in dev and prod.
> [2] A ***.env file*** is a simple `KEY=value` list, kept out of version control
> (it's in `.gitignore`) because it may hold machine- or secret-specific values.
> [3] Precedence (highest first): real env var → `.env` file → built-in default.
> Predictable precedence is what makes overrides trustworthy.

---

## Typed getters: fail loudly, fail early

Configuration is parsed through small helpers that validate as they read:

```python
def _get_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError as exc:
        raise ValueError(f"Env var {key!r} must be an integer, got {raw!r}") from exc
```

If someone sets `TOP_K=five`, the app stops immediately with a clear message —
instead of crashing mysteriously deep inside FAISS later.[1]

⚠️ **Pitfall:** reading env vars ad-hoc with `int(os.environ["TOP_K"])` scattered
around gives cryptic errors far from the cause. Centralized, validated getters turn
a confusing runtime crash into an obvious startup error.

> **Footnotes**
> [1] "Fail fast" is a design principle: detect an invalid state at the earliest,
> clearest point. `raise ... from exc` preserves the original error for debugging —
> the *exception chaining* pattern.

---

## Derived paths and no import side-effects

Two subtle but important choices:

```python
@property
def index_path(self) -> Path:
    return self.index_dir / "faq.faiss"

def ensure_directories() -> None:      # called explicitly at startup
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.index_dir.mkdir(parents=True, exist_ok=True)
```

- Artifact locations are **derived** from `index_dir`, so there's still one source
  of truth for *where things live*.[1]
- Creating folders is a **separate, explicit call** — importing `settings` has **no
  side effects**.[2]

> **Footnotes**
> [1] A ***property*** looks like an attribute but runs code. `settings.index_path`
> is always `index_dir/faq.faiss`; change the directory and the file follows.
> [2] A ***side effect*** is anything a piece of code does beyond returning a value
> (writing files, network calls). Import-time side effects make code hard to test
> and reason about; keeping imports pure is a deliberate discipline.

---

## Logging: configure once, use everywhere

```python
def get_logger(name: str) -> logging.Logger:
    configure_logging()               # no-op after the first call
    return logging.getLogger(name)
```

Every module does `logger = get_logger(__name__)` and then `logger.info(...)`.[1]
The format and level are set in exactly one place, mirroring the config philosophy.

🧠 **Nuance:** using `logging` instead of `print` means messages carry a level
(INFO/WARNING/ERROR), a timestamp, and the module name — and can be filtered or
silenced globally by changing `LOG_LEVEL`.

> **Footnotes**
> [1] `__name__` is the module's dotted path (e.g. `app.retrieval.index_manager`),
> so every log line tells you *where* it came from. A guard flag makes repeated
> `configure_logging()` calls harmless (idempotent setup).

---

## Recap & what's next

- All tunable values live in one **frozen** `Settings` object with **defaults +
  env overrides**.
- Getters **validate early**; paths are **derived**; imports have **no side
  effects**; logging is **configured once**.

🛠️ **Try it:** create a `.env` with `TOP_K=3` and restart the app. Ask a question
with Developer mode on — the alternatives list now shows at most 3 candidates. Then
try `TOP_K=abc` and watch the app refuse to start with a clear message.

**Next:** [Chapter 3 — The Database Layer](03-the-database-layer.md): SQLite as the
system of record, and the repository pattern that keeps SQL in one place.
