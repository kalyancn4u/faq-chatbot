"""Shared Streamlit helpers: cached resources, bootstrap, and small widgets.

Streamlit re-runs the whole script on every interaction, so anything expensive
(the embedding model, the loaded FAISS index) must be cached with
``st.cache_resource`` to avoid reloading each time. One shared
:class:`IndexManager` instance is used by both the chat and admin pages so that
an admin rebuild is immediately visible to search.
"""

from __future__ import annotations

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


def confidence_badge(level: ConfidenceLevel) -> None:
    """Render a small colored confidence badge."""
    color, label = _CONFIDENCE_STYLE.get(level, ("#6e7781", str(level)))
    st.markdown(
        f"<span style='background:{color};color:white;padding:2px 10px;"
        f"border-radius:12px;font-size:0.8rem;'>Confidence: {label}</span>",
        unsafe_allow_html=True,
    )
