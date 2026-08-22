"""Channel-aware reply formatting.

The same answer must be *presented* differently depending on where it is sent.
A messaging channel has hard rules — how bold text is written, whether emoji
survive, how long a message may be — and ignoring them makes replies look broken
or get rejected. This module takes one :class:`~app.services.faq_service.AnswerResult`
and renders a string tailored to a chosen :class:`Channel`.

Why a separate layer? Answering (what to say) and formatting (how to say it on a
given channel) are different jobs. Keeping them apart means we can add a channel
by adding one :class:`ChannelSpec` — no changes to the search or answering logic.
It is also the natural seam where a future version could actually *send* to
WhatsApp/Telegram, not just preview.

The channels and their key rules:

============  ===================  ==================  ==============  ===========
Channel       Bold syntax          Emoji               Max length      Notes
============  ===================  ==================  ==============  ===========
Chat window   ``**bold**``         yes                 unlimited       full Markdown
WhatsApp      ``*bold*``           yes                 ~4096           single-star bold
Telegram      ``*bold*`` (MDv2)    yes                 ~4096           reserved chars escaped
SMS           none (plain)         no (stripped)       160 / segment   segments of 153 chars
============  ===================  ==================  ==============  ===========

For SMS we also drop the "related questions" list: every character costs money in
segments, so the reply stays to the answer itself.
"""

from __future__ import annotations

import math
import re
from collections.abc import Callable
from dataclasses import dataclass
from enum import Enum

from app.services.faq_service import AnswerResult, ConfidenceLevel


class Channel(str, Enum):
    """A destination channel for the reply."""

    CHAT = "chat"
    WHATSAPP = "whatsapp"
    TELEGRAM = "telegram"
    SMS = "sms"


# --------------------------------------------------------------------------- #
# Text transformations
# --------------------------------------------------------------------------- #
# Common emoji / pictograph ranges plus the variation-selector and zero-width
# joiner used to compose them. Stripped for SMS, which cannot render emoji.
_EMOJI_RE = re.compile(
    "[\U0001F300-\U0001FAFF"  # symbols, pictographs, emoji
    "\U0001F000-\U0001F0FF"  # mahjong/dominoes/cards
    "\U0001F1E6-\U0001F1FF"  # regional indicators (flags)
    "\U00002600-\U000027BF"  # misc symbols + dingbats
    "\U00002B00-\U00002BFF"  # arrows/stars
    "\U0001F900-\U0001F9FF"  # supplemental symbols
    "️‍]",  # variation selector, ZWJ
    flags=re.UNICODE,
)

# Characters Telegram MarkdownV2 treats as special; each must be backslash-escaped
# in ordinary text or the Bot API rejects the message.
_TELEGRAM_SPECIAL = r"_*[]()~`>#+-=|{}.!\\"
_TELEGRAM_ESCAPE_RE = re.compile("([" + re.escape(_TELEGRAM_SPECIAL) + "])")


def strip_emoji(text: str) -> str:
    """Remove emoji/pictographs (used for SMS)."""
    return _EMOJI_RE.sub("", text)


def strip_markdown(text: str) -> str:
    """Reduce common Markdown to plain text (used for SMS)."""
    text = re.sub(r"\[([^\]]+)\]\([^)]+\)", r"\1", text)  # [label](url) -> label
    text = re.sub(r"[*_`~]+", "", text)  # bold/italic/code/strikethrough marks
    text = re.sub(r"(?m)^\s{0,3}#{1,6}\s*", "", text)  # heading markers
    text = re.sub(r"(?m)^\s*[-*+]\s+", "", text)  # list bullets
    return text


def escape_markdown_v2(text: str) -> str:
    r"""Backslash-escape Telegram MarkdownV2 special characters.

    Telegram requires this for any literal text sent with ``parse_mode=MarkdownV2``.
    For example ``3-5 days.`` becomes ``3\-5 days\.`` — the backslashes are part of
    the wire format and are *not* shown to the reader; Telegram renders plain text.
    """
    return _TELEGRAM_ESCAPE_RE.sub(r"\\\1", text)


def _collapse_ws(text: str) -> str:
    return re.sub(r"[ \t]+", " ", text).strip()


# --------------------------------------------------------------------------- #
# Channel specifications
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class ChannelSpec:
    """Formatting rules for one channel. Add a channel by adding one of these."""

    channel: Channel
    label: str  # human-facing name for the UI
    prepare: Callable[[str], str]  # how to sanitize literal text for this channel
    bold: Callable[[str], str]  # how to make a (safe, ASCII) label bold
    bullet: str
    max_length: int | None
    include_confidence: bool
    include_alternatives: bool
    max_alternatives: int
    is_sms: bool = False


def _identity(text: str) -> str:
    return text


def _sms_prepare(text: str) -> str:
    return _collapse_ws(strip_emoji(strip_markdown(text)))


CHANNELS: dict[Channel, ChannelSpec] = {
    Channel.CHAT: ChannelSpec(
        channel=Channel.CHAT,
        label="Chat window",
        prepare=_identity,
        bold=lambda s: f"**{s}**",
        bullet="-",
        max_length=None,
        include_confidence=True,
        include_alternatives=True,
        max_alternatives=3,
    ),
    Channel.WHATSAPP: ChannelSpec(
        channel=Channel.WHATSAPP,
        label="WhatsApp",
        prepare=_identity,  # keeps emoji; FAQ answers contain no markdown
        bold=lambda s: f"*{s}*",  # WhatsApp bold = single asterisks
        bullet="•",
        max_length=4096,
        include_confidence=True,
        include_alternatives=True,
        max_alternatives=3,
    ),
    Channel.TELEGRAM: ChannelSpec(
        channel=Channel.TELEGRAM,
        label="Telegram",
        prepare=escape_markdown_v2,  # MarkdownV2 requires escaping literal text
        bold=lambda s: f"*{s}*",  # labels here are plain ASCII, safe to bold as-is
        bullet="•",
        max_length=4096,
        include_confidence=True,
        include_alternatives=True,
        max_alternatives=3,
    ),
    Channel.SMS: ChannelSpec(
        channel=Channel.SMS,
        label="SMS",
        prepare=_sms_prepare,  # plain text, no emoji, no markdown
        bold=_identity,  # SMS has no formatting
        bullet="-",
        max_length=160,  # keep to a single segment
        include_confidence=False,  # every character costs a segment
        include_alternatives=False,
        max_alternatives=0,
        is_sms=True,
    ),
}

# Order the channels are offered in the UI.
ORDERED_CHANNELS: list[Channel] = [Channel.CHAT, Channel.WHATSAPP, Channel.TELEGRAM, Channel.SMS]
CHANNEL_LABELS: list[str] = [CHANNELS[c].label for c in ORDERED_CHANNELS]


def channel_from_label(label: str) -> Channel:
    """Map a UI label (e.g. ``"WhatsApp"``) back to its :class:`Channel`."""
    for channel, spec in CHANNELS.items():
        if spec.label == label:
            return channel
    return Channel.CHAT


# --------------------------------------------------------------------------- #
# Formatting
# --------------------------------------------------------------------------- #
@dataclass(frozen=True)
class FormattedReply:
    """A reply rendered for one channel, plus metadata for verification."""

    channel: Channel
    channel_label: str
    text: str
    char_count: int
    original_length: int
    truncated: bool
    max_length: int | None
    sms_segments: int | None  # only set for SMS


def _sms_segments(length: int) -> int:
    """GSM-7 segment count: one message up to 160 chars, else 153 chars each."""
    if length == 0:
        return 0
    if length <= 160:
        return 1
    return math.ceil(length / 153)


_SHOWN_CONFIDENCE = (ConfidenceLevel.HIGH, ConfidenceLevel.MEDIUM, ConfidenceLevel.LOW)


def format_reply(result: AnswerResult, channel: Channel) -> FormattedReply:
    """Render ``result`` for ``channel``.

    The answer text is sanitized for the channel, an optional confidence line and
    a "related questions" list are appended where the channel allows, and the
    whole thing is truncated to the channel's length limit if needed.
    """
    spec = CHANNELS[channel]

    parts: list[str] = [spec.prepare(result.answer)]

    if spec.include_confidence and result.confidence_level in _SHOWN_CONFIDENCE:
        parts.append(f"{spec.bold('Confidence:')} {result.confidence_level.value}")

    if spec.include_alternatives and result.alternative_matches:
        header = "Related questions:" if result.is_answered else "You might mean:"
        lines = [spec.bold(header)]
        for alt in result.alternative_matches[: spec.max_alternatives]:
            lines.append(f"{spec.bullet} {spec.prepare(alt.question)}")
        parts.append("\n".join(lines))

    body = "\n\n".join(parts)
    original_length = len(body)

    truncated = False
    if spec.max_length is not None and original_length > spec.max_length:
        ellipsis = "..." if spec.is_sms else "…"
        keep = spec.max_length - len(ellipsis)
        body = body[:keep].rstrip() + ellipsis
        truncated = True

    return FormattedReply(
        channel=channel,
        channel_label=spec.label,
        text=body,
        char_count=len(body),
        original_length=original_length,
        truncated=truncated,
        max_length=spec.max_length,
        sms_segments=_sms_segments(original_length) if spec.is_sms else None,
    )
