"""Centralized, environment-overridable configuration.

Every tunable value in the project lives here so nothing is hard-coded across
modules. Values are read once at import time from environment variables (loaded
from a local ``.env`` if present) and exposed as a frozen ``Settings`` instance.

Import pattern used throughout the codebase::

    from app.config.settings import settings
    model_name = settings.embedding_model_name

Why a single module: FAQ retrieval quality depends on a handful of knobs
(``TOP_K``, similarity thresholds, model name). Keeping them in one place makes
them easy to find, document, and tune. Thresholds in particular are *empirical*
— the defaults below are reasonable starting points, not universal truths, and
should be re-tuned against your own FAQ data.
"""

from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

from dotenv import load_dotenv

# Project root = two levels up from this file (app/config/settings.py -> repo root).
PROJECT_ROOT: Path = Path(__file__).resolve().parents[2]

# Load .env from the project root if it exists. Real environment variables that
# are already set always win (override=False), which is the standard precedence.
load_dotenv(PROJECT_ROOT / ".env", override=False)


def _get_str(key: str, default: str) -> str:
    value = os.getenv(key)
    return value if value not in (None, "") else default


def _get_bool(key: str, default: bool) -> bool:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    return raw.strip().lower() in ("1", "true", "yes", "on")


def _get_int(key: str, default: int) -> int:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    try:
        return int(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Env var {key!r} must be an integer, got {raw!r}") from exc


def _get_float(key: str, default: float) -> float:
    raw = os.getenv(key)
    if raw in (None, ""):
        return default
    try:
        return float(raw)
    except ValueError as exc:  # pragma: no cover - defensive
        raise ValueError(f"Env var {key!r} must be a float, got {raw!r}") from exc


def _resolve(path_str: str) -> Path:
    """Resolve a path relative to the project root unless it is absolute."""
    path = Path(path_str)
    return path if path.is_absolute() else (PROJECT_ROOT / path)


@dataclass(frozen=True)
class Settings:
    """Immutable snapshot of all configuration for one process run."""

    # --- Embedding model ---
    embedding_model_name: str

    # --- Retrieval / confidence ---
    top_k: int
    similarity_threshold_high: float
    similarity_threshold_low: float

    # --- Paths ---
    db_path: Path
    index_dir: Path

    # --- Logging ---
    log_level: str

    # --- Hugging Face ---
    # When True, load the embedding model from the local cache only and skip all
    # network checks. Useful once the model is cached, and essential on networks
    # that intercept TLS to huggingface.co (avoids a slow retry storm on startup).
    hf_offline: bool

    # Derived, stable artifact locations inside index_dir.
    @property
    def index_path(self) -> Path:
        """Path to the serialized FAISS index file."""
        return self.index_dir / "faq.faiss"

    @property
    def id_map_path(self) -> Path:
        """Path to the FAISS-row -> SQLite-FAQ-id mapping file."""
        return self.index_dir / "id_map.json"


def _build_settings() -> Settings:
    return Settings(
        embedding_model_name=_get_str("EMBEDDING_MODEL_NAME", "all-MiniLM-L6-v2"),
        top_k=_get_int("TOP_K", 5),
        similarity_threshold_high=_get_float("SIMILARITY_THRESHOLD_HIGH", 0.65),
        similarity_threshold_low=_get_float("SIMILARITY_THRESHOLD_LOW", 0.45),
        db_path=_resolve(_get_str("DB_PATH", "data/database/faq.db")),
        index_dir=_resolve(_get_str("INDEX_DIR", "data/indexes")),
        log_level=_get_str("LOG_LEVEL", "INFO").upper(),
        hf_offline=_get_bool("HF_OFFLINE", False),
    )


# Single shared instance imported everywhere.
settings: Settings = _build_settings()

# Apply Hugging Face offline mode as early as possible (before transformers /
# huggingface_hub read these at import time), so a cached model loads instantly
# and no network call is attempted.
if settings.hf_offline:
    os.environ.setdefault("HF_HUB_OFFLINE", "1")
    os.environ.setdefault("TRANSFORMERS_OFFLINE", "1")


def ensure_directories() -> None:
    """Create the data directories the app writes to, if they do not exist.

    Safe to call at startup and repeatedly; creating an existing directory is a
    no-op. Kept explicit (rather than done at import) so importing settings has
    no filesystem side effects.
    """
    settings.db_path.parent.mkdir(parents=True, exist_ok=True)
    settings.index_dir.mkdir(parents=True, exist_ok=True)
