"""Shared Streamlit helpers: cached resources, bootstrap, and small widgets.

Streamlit re-runs the whole script on every interaction, so anything expensive
(the embedding model, the loaded FAISS index) must be cached with
``st.cache_resource`` to avoid reloading each time. One shared
:class:`IndexManager` instance is used by both the chat and admin pages so that
an admin rebuild is immediately visible to search.
"""

from __future__ import annotations

import html

import streamlit as st

from app.config.logging_config import get_logger
from app.config.settings import ensure_directories
from app.database.connection import get_connection
from app.database.repository import FAQRepository
from app.database.schema import initialize_database
from app.retrieval.index_manager import IndexManager
from app.services.faq_service import ConfidenceLevel

logger = get_logger(__name__)

_CONFIDENCE_STYLE = {
    ConfidenceLevel.HIGH: ("#1a7f37", "High"),
    ConfidenceLevel.MEDIUM: ("#9a6700", "Medium"),
    ConfidenceLevel.LOW: ("#b35900", "Low"),
    ConfidenceLevel.NONE: ("#6e7781", "None"),
}


@st.cache_resource(show_spinner=False)
def get_index_manager() -> IndexManager:
    """Return the process-wide shared index manager (holds the loaded index)."""
    return IndexManager()


@st.cache_resource(show_spinner="Preparing the FAQ database and index...")
def bootstrap() -> bool:
    """Ensure the database schema exists and the index is built (once per run).

    Safe and idempotent. If there are active FAQs but no index yet, build it so
    the chat works on first launch without a manual step.
    """
    ensure_directories()
    manager = get_index_manager()
    with get_connection() as conn:
        initialize_database(conn)
        active = FAQRepository(conn).count_active()
        if active and manager.is_stale(conn):
            logger.info("Building FAISS index at startup (%d active FAQs).", active)
            manager.rebuild(conn)
    return True


# Markdown-significant characters mapped to numeric HTML entities. Rendering
# these as entities makes Streamlit's Markdown parser leave them alone (so
# `*bold*` and Telegram's `\.` show literally), while the browser still displays
# the intended glyph. Without this, st.markdown would italicize `*...*` and drop
# backslash escapes — misrepresenting what the channel actually sends.
_MD_NEUTRALIZE = {
    "\\": "&#92;",
    "*": "&#42;",
    "_": "&#95;",
    "`": "&#96;",
    "~": "&#126;",
    "[": "&#91;",
    "]": "&#93;",
}


def escape_literal(text: str) -> str:
    r"""HTML-escape text and entity-encode Markdown characters for literal display.

    Used wherever raw content is placed inside ``st.markdown`` HTML: escapes
    ``& < >`` (so it cannot inject markup) and encodes ``\ * _ ` ~ [ ]`` as
    entities so Streamlit's Markdown parser renders them as themselves.
    """
    out = html.escape(str(text), quote=False)
    for char, entity in _MD_NEUTRALIZE.items():
        out = out.replace(char, entity)
    return out


def channel_preview_box(text: str) -> None:
    """Render channel-formatted text exactly as it would be sent.

    Uses a monospace ``<pre>`` so raw markers (``*bold*``, escaped ``\\.``) show
    literally, but with ``white-space: pre-wrap`` + word breaking so long lines
    **wrap** instead of overflowing, and ``width:100%`` so the box is responsive —
    it reflows as the browser window changes size. Colors use translucent tones
    so it reads well in both light and dark themes.
    """
    escaped = escape_literal(text)
    st.markdown(
        f"""
<div style="
    border:1px solid rgba(128,128,128,0.35);
    background:rgba(128,128,128,0.10);
    border-radius:12px;
    padding:12px 14px;
    max-width:100%;
    box-sizing:border-box;
">
  <pre style="
    margin:0;
    white-space:pre-wrap;
    overflow-wrap:anywhere;
    word-break:break-word;
    font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,'Liberation Mono',monospace;
    font-size:0.9rem;
    line-height:1.5;
  ">{escaped}</pre>
</div>
""",
        unsafe_allow_html=True,
    )


def build_candidates_table_html(rows: list[dict]) -> str:
    """Build a responsive, wrapping HTML table of retrieval candidates.

    Pure function (no Streamlit) so it can be unit-tested. Each row is a dict with
    ``faq_id``, ``question`` and ``score``. ``table-layout:fixed`` plus
    ``word-break``/``overflow-wrap`` on cells make long questions **wrap** instead
    of overflowing; the whole table is ``width:100%`` and wrapped in an
    ``overflow-x:auto`` container as a final safety net, so it stays responsive.
    """
    body = ""
    for r in rows:
        question = escape_literal(r.get("question", ""))
        score = r.get("score", "")
        score_str = f"{score:.4f}" if isinstance(score, (int, float)) else escape_literal(score)
        body += (
            f"<tr><td>{escape_literal(r.get('faq_id', ''))}</td>"
            f"<td>{question}</td><td>{score_str}</td></tr>"
        )
    return f"""
<div class="faq-diag" style="overflow-x:auto;max-width:100%;">
  <style>
    .faq-diag table {{ width:100%; border-collapse:collapse; table-layout:fixed; font-size:0.85rem; }}
    .faq-diag th, .faq-diag td {{
        text-align:left; padding:6px 8px; vertical-align:top;
        border-bottom:1px solid rgba(128,128,128,0.25);
        word-break:break-word; overflow-wrap:anywhere; white-space:normal;
    }}
    .faq-diag th {{ background:rgba(128,128,128,0.12); font-weight:600; }}
    .faq-diag col.c-id {{ width:64px; }}
    .faq-diag col.c-score {{ width:84px; }}
  </style>
  <table>
    <colgroup><col class="c-id"><col class="c-q"><col class="c-score"></colgroup>
    <thead><tr><th>faq_id</th><th>question</th><th>score</th></tr></thead>
    <tbody>{body}</tbody>
  </table>
</div>
"""


def candidates_table(rows: list[dict]) -> None:
    """Render the responsive retrieval-candidates table (see builder)."""
    st.markdown(build_candidates_table_html(rows), unsafe_allow_html=True)


def confidence_badge(level: ConfidenceLevel) -> None:
    """Render a small colored confidence badge."""
    color, label = _CONFIDENCE_STYLE.get(level, ("#6e7781", str(level)))
    st.markdown(
        f"<span style='background:{color};color:white;padding:2px 10px;"
        f"border-radius:12px;font-size:0.8rem;'>Confidence: {label}</span>",
        unsafe_allow_html=True,
    )
