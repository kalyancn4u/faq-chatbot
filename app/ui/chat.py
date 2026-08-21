"""Chat page: ask a question, get a curated answer with confidence handling."""

from __future__ import annotations

import streamlit as st

from app.database.connection import get_connection
from app.services.faq_service import AnswerResult, AnswerStatus, FAQService
from app.services.feedback_service import FeedbackService
from app.ui.components import confidence_badge, get_index_manager
from app.retrieval.search import SemanticSearch


def _answer(question: str) -> AnswerResult:
    with get_connection() as conn:
        service = FAQService(conn, search=SemanticSearch(index_manager=get_index_manager()))
        return service.answer_question(question)


def _record_feedback(result: AnswerResult, was_helpful: bool) -> None:
    with get_connection() as conn:
        FeedbackService(conn).record(
            user_question=result.user_question,
            faq_id=result.matched_faq_id,
            similarity_score=result.similarity_score,
            was_helpful=was_helpful,
        )


def _render_turn(index: int, entry: dict, dev_mode: bool) -> None:
    result: AnswerResult = entry["result"]

    with st.chat_message("user"):
        st.write(result.user_question)

    with st.chat_message("assistant"):
        st.write(result.answer)
        confidence_badge(result.confidence_level)

        if result.status is AnswerStatus.ANSWER_FOUND and dev_mode and result.matched_question:
            st.caption(f"Matched: “{result.matched_question}” (id {result.matched_faq_id})")

        # Suggested related questions.
        if result.alternative_matches:
            label = (
                "Related topics you might mean:"
                if result.status is not AnswerStatus.ANSWER_FOUND
                else "Related questions:"
            )
            st.caption(label)
            for alt in result.alternative_matches[:3]:
                st.markdown(f"- {alt.question}")

        # Feedback controls (only where a match was involved).
        if result.status in (AnswerStatus.ANSWER_FOUND, AnswerStatus.LOW_CONFIDENCE):
            _render_feedback(index, entry, result)

        # Developer diagnostics.
        if dev_mode:
            _render_diagnostics(result)


def _render_feedback(index: int, entry: dict, result: AnswerResult) -> None:
    if entry["feedback"] is not None:
        st.caption("👍 Thanks for the feedback!" if entry["feedback"] else "👎 Thanks — we'll use this to improve.")
        return

    st.caption("Was this helpful?")
    col_yes, col_no, _ = st.columns([1, 1, 6])
    if col_yes.button("👍 Yes", key=f"fb_yes_{index}"):
        _record_feedback(result, True)
        st.session_state.history[index]["feedback"] = True
        st.rerun()
    if col_no.button("👎 No", key=f"fb_no_{index}"):
        _record_feedback(result, False)
        st.session_state.history[index]["feedback"] = False
        st.rerun()


def _render_diagnostics(result: AnswerResult) -> None:
    with st.expander("Developer diagnostics"):
        st.write(
            {
                "status": result.status.value,
                "confidence": result.confidence_level.value,
                "matched_faq_id": result.matched_faq_id,
                "similarity_score": result.similarity_score,
            }
        )
        if result.alternative_matches:
            st.table(
                [
                    {"faq_id": a.faq_id, "question": a.question, "score": round(a.score, 4)}
                    for a in result.alternative_matches
                ]
            )


def render_chat_page(dev_mode: bool = False) -> None:
    """Render the chat interface."""
    st.subheader("Ask a question")
    st.caption("Type a question in your own words — the bot matches it to a curated FAQ.")

    st.session_state.setdefault("history", [])

    for i, entry in enumerate(st.session_state.history):
        _render_turn(i, entry, dev_mode)

    prompt = st.chat_input("e.g. I can't remember my password")
    if prompt:
        result = _answer(prompt)
        st.session_state.history.append({"result": result, "feedback": None})
        st.rerun()
