"""Streamlit entrypoint.

Run with::

    streamlit run app/main.py

On first launch it ensures the database schema exists and builds the FAISS index
if needed, then serves two pages selected from the sidebar: the user-facing Chat
page and the Admin page. A "Developer mode" toggle reveals retrieval diagnostics
on the chat page for troubleshooting.
"""

from __future__ import annotations

import streamlit as st

from app.services.response_formatter import CHANNEL_LABELS, channel_from_label
from app.ui.admin import render_admin_page
from app.ui.chat import render_chat_page
from app.ui.components import bootstrap


def main() -> None:
    st.set_page_config(page_title="Semantic FAQ Chatbot", page_icon="💬", layout="centered")
    bootstrap()

    st.title("💬 Semantic FAQ Chatbot")

    with st.sidebar:
        st.header("Navigation")
        page = st.radio("Page", ["Chat", "Admin"], label_visibility="collapsed")
        st.divider()
        channel_label = st.selectbox(
            "Reply format",
            options=CHANNEL_LABELS,
            index=0,
            help="Preview the reply as it would be sent on each channel.",
        )
        dev_mode = st.toggle("Developer mode", value=False, help="Show retrieval diagnostics.")
        st.caption("Local-first · SQLite + FAISS + Sentence Transformers")

    if page == "Chat":
        render_chat_page(channel=channel_from_label(channel_label), dev_mode=dev_mode)
    else:
        render_admin_page()


if __name__ == "__main__":
    main()
