"""Admin page: manage FAQs, import/export, rebuild the index, review activity.

Aimed at a non-ML administrator: the mental model is simply "edit FAQs, then
rebuild the index so changes become searchable." Destructive actions require an
explicit confirmation, and soft-deactivate is offered as the safer default.
"""

from __future__ import annotations

import tempfile
from pathlib import Path

import streamlit as st

from app.database.connection import get_connection
from app.database.repository import FeedbackRepository, UnansweredRepository
from app.retrieval.index_manager import IndexConsistencyError
from app.services.admin_service import AdminService
from app.ui.components import get_index_manager


def _service(conn) -> AdminService:
    return AdminService(conn, index_manager=get_index_manager())


def _parse_tags(raw: str) -> list[str]:
    return [t.strip() for t in raw.split(",") if t.strip()]


def render_admin_page() -> None:
    """Render the admin interface."""
    st.subheader("Admin")
    st.caption("Manage FAQs and the search index. Rebuild the index after making changes.")

    tab_faqs, tab_io, tab_index, tab_unanswered, tab_feedback = st.tabs(
        ["FAQs", "Import / Export", "Index", "Unanswered", "Feedback"]
    )

    with tab_faqs:
        _render_faqs_tab()
    with tab_io:
        _render_io_tab()
    with tab_index:
        _render_index_tab()
    with tab_unanswered:
        _render_unanswered_tab()
    with tab_feedback:
        _render_feedback_tab()


# --------------------------------------------------------------------------- #
# FAQs
# --------------------------------------------------------------------------- #
def _render_faqs_tab() -> None:
    st.markdown("#### Add a new FAQ")
    with st.form("add_faq", clear_on_submit=True):
        question = st.text_input("Question")
        answer = st.text_area("Answer")
        col1, col2 = st.columns(2)
        category = col1.text_input("Category", value="General")
        tags = col2.text_input("Tags (comma-separated)")
        submitted = st.form_submit_button("Add FAQ")
    if submitted:
        try:
            with get_connection() as conn:
                _service(conn).add_faq(question, answer, category, _parse_tags(tags))
            st.success("FAQ added. Rebuild the index (Index tab) to make it searchable.")
        except ValueError as exc:
            st.error(str(exc))

    st.divider()
    st.markdown("#### Existing FAQs")
    term = st.text_input("Search FAQs", key="faq_search")
    with get_connection() as conn:
        svc = _service(conn)
        faqs = svc.search_faqs(term) if term.strip() else svc.list_faqs()

    if not faqs:
        st.info("No FAQs found.")
        return

    st.dataframe(
        [
            {
                "id": f.id,
                "active": "✓" if f.is_active else "—",
                "question": f.question,
                "category": f.category,
            }
            for f in faqs
        ],
        use_container_width=True,
        hide_index=True,
    )

    _render_edit_section({f.id: f for f in faqs})


def _render_edit_section(faqs_by_id: dict) -> None:
    st.markdown("#### Edit / remove an FAQ")
    ids = list(faqs_by_id.keys())
    faq_id = st.selectbox(
        "Select FAQ",
        options=ids,
        format_func=lambda i: f"[{i}] {faqs_by_id[i].question}",
    )
    faq = faqs_by_id[faq_id]

    with st.form(f"edit_{faq_id}"):
        question = st.text_input("Question", value=faq.question)
        answer = st.text_area("Answer", value=faq.answer)
        col1, col2 = st.columns(2)
        category = col1.text_input("Category", value=faq.category)
        tags = col2.text_input("Tags (comma-separated)", value=", ".join(faq.tags))
        save = st.form_submit_button("Save changes")
    if save:
        try:
            with get_connection() as conn:
                _service(conn).update_faq(
                    faq_id,
                    question=question,
                    answer=answer,
                    category=category,
                    tags=_parse_tags(tags),
                )
            st.success("Saved. Rebuild the index to apply changes to search.")
        except ValueError as exc:
            st.error(str(exc))

    col_a, col_b = st.columns(2)
    with col_a:
        toggle_label = "Deactivate" if faq.is_active else "Activate"
        if st.button(f"{toggle_label} (safe)", key=f"toggle_{faq_id}"):
            with get_connection() as conn:
                _service(conn).set_active(faq_id, not faq.is_active)
            st.success(f"FAQ {toggle_label.lower()}d. Rebuild the index to apply.")
            st.rerun()
    with col_b:
        confirm = st.checkbox("Confirm permanent delete", key=f"confirm_{faq_id}")
        if st.button("Delete permanently", key=f"delete_{faq_id}", disabled=not confirm):
            with get_connection() as conn:
                _service(conn).delete_faq(faq_id)
            st.warning("FAQ deleted. Rebuild the index to apply.")
            st.rerun()


# --------------------------------------------------------------------------- #
# Import / Export
# --------------------------------------------------------------------------- #
def _render_io_tab() -> None:
    st.markdown("#### Import FAQs from CSV")
    st.caption("Columns: question, answer, category, tags (pipe-separated). Rows are validated first.")
    uploaded = st.file_uploader("Choose a CSV file", type="csv")
    if uploaded is not None and st.button("Import"):
        with tempfile.NamedTemporaryFile(delete=False, suffix=".csv") as tmp:
            tmp.write(uploaded.getvalue())
            tmp_path = tmp.name
        try:
            with get_connection() as conn:
                result = _service(conn).import_csv(tmp_path)
            st.success(
                f"Imported {result.inserted} FAQ(s); "
                f"{result.skipped_duplicate} duplicate(s), {result.skipped_invalid} invalid skipped."
            )
            for err in result.errors[:10]:
                st.caption(f"• {err}")
            if result.inserted:
                st.info("Rebuild the index (Index tab) to make new FAQs searchable.")
        finally:
            Path(tmp_path).unlink(missing_ok=True)

    st.divider()
    st.markdown("#### Export FAQs to CSV")
    with get_connection() as conn:
        csv_text = _service(conn).export_csv()
    st.download_button("Download faqs.csv", data=csv_text, file_name="faqs.csv", mime="text/csv")


# --------------------------------------------------------------------------- #
# Index
# --------------------------------------------------------------------------- #
def _render_index_tab() -> None:
    st.markdown("#### Search index status")
    with get_connection() as conn:
        status = _service(conn).index_status()

    cols = st.columns(3)
    cols[0].metric("Indexed vectors", status.indexed_vectors)
    cols[1].metric("Mapped ids", status.mapped_ids)
    cols[2].metric("Active FAQs", status.active_faqs)
    st.write(
        {
            "exists": status.exists,
            "stale (needs rebuild)": status.is_stale,
            "model": status.model_name,
            "dimension": status.dimension,
        }
    )
    if status.is_stale:
        st.warning("The index is stale or missing. Rebuild it to reflect the current FAQs.")
    else:
        st.success("The index is consistent with the active FAQs.")

    if st.button("Rebuild index now"):
        try:
            with get_connection() as conn:
                result = _service(conn).rebuild_index()
            st.success(f"Rebuilt: {result.faq_count} FAQs indexed (dim {result.dimension}).")
            st.rerun()
        except (ValueError, IndexConsistencyError) as exc:
            st.error(str(exc))


# --------------------------------------------------------------------------- #
# Unanswered
# --------------------------------------------------------------------------- #
def _render_unanswered_tab() -> None:
    st.markdown("#### Unanswered / low-confidence questions")
    only_unreviewed = st.toggle("Show only unreviewed", value=True)
    with get_connection() as conn:
        items = UnansweredRepository(conn).list(only_unreviewed=only_unreviewed)

    if not items:
        st.info("Nothing to review.")
        return

    for item in items:
        col1, col2, col3 = st.columns([6, 2, 2])
        col1.write(item.question)
        score = "—" if item.best_similarity_score is None else f"{item.best_similarity_score:.3f}"
        col2.caption(f"best: {score}")
        if not item.reviewed:
            if col3.button("Mark reviewed", key=f"rev_{item.id}"):
                with get_connection() as conn:
                    UnansweredRepository(conn).mark_reviewed(item.id)
                st.rerun()
        else:
            col3.caption("reviewed ✓")


# --------------------------------------------------------------------------- #
# Feedback
# --------------------------------------------------------------------------- #
def _render_feedback_tab() -> None:
    st.markdown("#### Recent feedback")
    with get_connection() as conn:
        rows = FeedbackRepository(conn).list_recent(limit=100)

    if not rows:
        st.info("No feedback yet.")
        return

    st.dataframe(
        [
            {
                "when": r.created_at,
                "question": r.user_question,
                "faq_id": r.faq_id,
                "score": None if r.similarity_score is None else round(r.similarity_score, 4),
                "helpful": {True: "👍", False: "👎", None: "—"}[r.was_helpful],
            }
            for r in rows
        ],
        use_container_width=True,
        hide_index=True,
    )
