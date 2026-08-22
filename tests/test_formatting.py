"""Tests for channel-aware reply formatting (no model needed — pure functions)."""

from __future__ import annotations

from app.services.faq_service import (
    AlternativeMatch,
    AnswerResult,
    AnswerStatus,
    ConfidenceLevel,
)
from app.services.response_formatter import (
    Channel,
    channel_from_label,
    escape_markdown_v2,
    format_reply,
    strip_emoji,
    strip_markdown,
)


def _answer(answer: str, *, status=AnswerStatus.ANSWER_FOUND, confidence=ConfidenceLevel.HIGH):
    return AnswerResult(
        user_question="how do I reset my password",
        status=status,
        answer=answer,
        confidence_level=confidence,
        matched_faq_id=1,
        matched_question="How do I reset my password?",
        similarity_score=0.92,
        alternative_matches=[
            AlternativeMatch(faq_id=2, question="I forgot my password.", score=0.88),
            AlternativeMatch(faq_id=3, question="I can't remember my login credentials.", score=0.81),
        ],
    )


# --- helper transforms ----------------------------------------------------- #
def test_strip_emoji_removes_pictographs_but_keeps_text():
    assert strip_emoji("Reset 🔒 now ✅") .replace("  ", " ").strip() == "Reset now"


def test_strip_markdown_removes_emphasis_and_links():
    assert strip_markdown("**bold** and [click](http://x)") == "bold and click"


def test_escape_markdown_v2_escapes_reserved():
    assert escape_markdown_v2("3-5 days.") == r"3\-5 days\."
    assert escape_markdown_v2("Settings > Billing") == r"Settings \> Billing"


# --- channel formatting ---------------------------------------------------- #
def test_chat_uses_double_star_bold_and_keeps_alternatives():
    out = format_reply(_answer("Click Forgot Password."), Channel.CHAT)
    assert "**Confidence:**" in out.text
    assert "Related questions:" in out.text
    assert "I forgot my password." in out.text
    assert out.max_length is None


def test_whatsapp_uses_single_star_bold():
    out = format_reply(_answer("Click Forgot Password."), Channel.WHATSAPP)
    assert "*Confidence:*" in out.text
    assert "**Confidence:**" not in out.text  # not double-star
    assert "•" in out.text  # bullet


def test_whatsapp_keeps_emoji_sms_does_not():
    wa = format_reply(_answer("Reset your password 🔒 now."), Channel.WHATSAPP)
    sms = format_reply(_answer("Reset your password 🔒 now."), Channel.SMS)
    assert "🔒" in wa.text
    assert "🔒" not in sms.text


def test_telegram_escapes_reserved_characters():
    out = format_reply(_answer("Go to Settings > Billing (30-day)."), Channel.TELEGRAM)
    assert r"\>" in out.text
    assert r"\-" in out.text
    assert r"\." in out.text
    assert "*Confidence:*" in out.text  # bold label still present


def test_sms_is_plain_and_drops_extras():
    out = format_reply(_answer("Click Forgot Password on the login page."), Channel.SMS)
    assert "*" not in out.text
    assert "Confidence" not in out.text  # dropped to save length
    assert "Related questions" not in out.text
    assert out.sms_segments == 1


def test_sms_truncates_long_answer_and_counts_segments():
    long_answer = "word " * 100  # 500 chars, well over 160
    out = format_reply(_answer(long_answer), Channel.SMS)
    assert out.truncated is True
    assert out.char_count <= 160
    assert out.text.endswith("...")
    assert out.original_length > 160
    assert out.sms_segments >= 2  # segment count is based on the original length


def test_low_confidence_alternatives_use_you_might_mean_header():
    result = _answer(
        "I couldn't find a reliable answer.",
        status=AnswerStatus.LOW_CONFIDENCE,
        confidence=ConfidenceLevel.LOW,
    )
    out = format_reply(result, Channel.WHATSAPP)
    assert "You might mean:" in out.text


def test_channel_from_label_roundtrip():
    assert channel_from_label("WhatsApp") is Channel.WHATSAPP
    assert channel_from_label("SMS") is Channel.SMS
    assert channel_from_label("Chat window") is Channel.CHAT
    assert channel_from_label("unknown") is Channel.CHAT  # safe default
