"""Tests for pure UI helper functions (no Streamlit runtime needed)."""

from __future__ import annotations

from app.ui.components import build_candidates_table_html, escape_literal


def test_escape_literal_neutralizes_markup_and_markdown():
    out = escape_literal("<b>*x*_y_</b> & done")
    assert "&lt;b&gt;" in out  # HTML escaped, cannot inject markup
    assert "&#42;" in out  # asterisk entity-encoded (won't italicize)
    assert "&#95;" in out  # underscore entity-encoded
    assert "&amp;" in out  # ampersand escaped
    assert "<b>" not in out


def test_candidates_table_is_responsive_and_wrapping():
    html = build_candidates_table_html(
        [{"faq_id": 1, "question": "How do I reset my password?", "score": 0.9123}]
    )
    # Responsive + wrapping CSS is present.
    assert "table-layout:fixed" in html
    assert "word-break:break-word" in html
    assert "overflow-wrap:anywhere" in html
    assert "overflow-x:auto" in html  # safety-net scroll container
    assert "width:100%" in html
    # Content rendered, score formatted to 4 dp.
    assert "How do I reset my password?" in html
    assert "0.9123" in html


def test_candidates_table_escapes_cell_content():
    html = build_candidates_table_html(
        [{"faq_id": 2, "question": "<script>alert(1)</script> *bold*", "score": 0.5}]
    )
    assert "<script>" not in html  # escaped, not injected
    assert "&lt;script&gt;" in html
    assert "&#42;bold&#42;" in html  # asterisks entity-encoded, shown literally
