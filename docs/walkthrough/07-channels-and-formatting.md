# Chapter 7 — Channels & Formatting

*One answer, correctly shaped for wherever it is sent.*

**By the end of this chapter you will be able to:** explain why channels need
different formatting, read the `ChannelSpec` design, understand Telegram's MarkdownV2
escaping and SMS segments, and add a new channel in three steps.

File: [`app/services/response_formatter.py`](../../app/services/response_formatter.py).
Companion guide: [docs/CHANNELS.md](../CHANNELS.md).

---

## Why one answer isn't enough

The bot has *one* answer, but **where** it's delivered changes **how** it must be
written:[1]

| Channel | Bold | Emoji | Length limit | Special rule |
|---------|------|-------|--------------|--------------|
| Chat window | `**bold**` | yes | none | full Markdown |
| WhatsApp | `*bold*` | yes | ~4096 | single-asterisk bold |
| Telegram | `*bold*` | yes | ~4096 | escape `. - ( ) ! >` … |
| SMS | none | no | 160 / segment | plain text only |

Ignore these and a WhatsApp reply shows literal `**`, an SMS costs double, and a
Telegram send is **rejected**.[2]

> **Footnotes**
> [1] This separates *what to say* (Chapter 6) from *how to write it here*. The answer
> is decided once; formatting is a pure transformation on top.
> [2] Telegram's API validates MarkdownV2 strictly; an unescaped `.` makes the whole
> send fail. SMS is billed per 160-character *segment*. These are real constraints,
> not style preferences.

---

## The design: rules as data (`ChannelSpec`)

Instead of `if channel == ...` branches everywhere, each channel is **one small data
object** describing its rules:[1]

```python
@dataclass(frozen=True)
class ChannelSpec:
    channel: Channel
    label: str
    prepare: Callable[[str], str]     # how to sanitize literal text
    bold: Callable[[str], str]        # how to make a label bold
    bullet: str
    max_length: int | None
    include_confidence: bool
    include_alternatives: bool
    max_alternatives: int
    is_sms: bool = False
```

`format_reply` then runs the **same four steps** for every channel: sanitize →
optionally add confidence + related list → join → truncate. The logic never grows
when you add a channel.[2]

> **Footnotes**
> [1] This is *data-driven design* (a.k.a. a strategy table): behavior lives in data,
> not in a growing chain of conditionals. Adding a channel is adding a row, not
> editing logic — fewer places to break.
> [2] `prepare` and `bold` are **functions stored in a field** (Python treats
> functions as values). Each channel plugs in its own text-cleaning and bold style.

---

## SMS: the strictest channel

SMS strips everything and counts the cost:

```python
def _sms_prepare(text):
    return _collapse_ws(strip_emoji(strip_markdown(text)))   # plain, no emoji

# spec: max_length=160, include_confidence=False, include_alternatives=False
```

- **No emoji** (classic SMS can't render them), **no markdown**, extras **dropped**
  to save space.[1]
- Over 160 characters it **truncates** with `...` and reports how many *segments* the
  full message would have taken.[2]

```python
def _sms_segments(length):
    if length <= 160: return 1
    return math.ceil(length / 153)     # multipart segments are 153 chars each
```

> **Footnotes**
> [1] On SMS every character costs money in segments, so the kindest reply is the
> answer alone. This is a *product* decision encoded as config (`include_* = False`).
> [2] A single SMS holds 160 GSM-7 characters; longer messages split into 153-char
> segments (7 chars go to joining headers). The app shows the segment count so you
> see the real cost.

---

## Telegram: escaping is not optional

Telegram's MarkdownV2 treats many punctuation marks as special. Literal text must
**backslash-escape** them or the API rejects the message:[1]

```python
_TELEGRAM_SPECIAL = r"_*[]()~`>#+-=|{}.!\\"

def escape_markdown_v2(text):
    return _TELEGRAM_ESCAPE_RE.sub(r"\\\1", text)   # "3-5 days." -> "3\-5 days\."
```

The backslashes are part of the **wire format**, not shown to the reader — Telegram
strips them and renders clean prose.[2]

⚠️ **Pitfall:** forgetting to escape is the most common Telegram-bot bug — sends
silently fail. The formatter does it for you via each channel's `prepare`.

> **Footnotes**
> [1] ***MarkdownV2*** is Telegram's strict markdown dialect (chosen with
> `parse_mode="MarkdownV2"` when actually sending). It's stricter than the "legacy"
> Markdown precisely so rendering is unambiguous.
> [2] The bold *labels* (e.g. `*Confidence:*`) are plain ASCII, safe to bold without
> escaping; only the dynamic content is escaped. That's why the formatter separates
> `bold(label)` from `prepare(text)`.

---

## Assembling the reply

```python
def format_reply(result, channel):
    spec = CHANNELS[channel]
    parts = [spec.prepare(result.answer)]
    if spec.include_confidence and result.confidence_level in _SHOWN:
        parts.append(f"{spec.bold('Confidence:')} {result.confidence_level.value}")
    if spec.include_alternatives and result.alternative_matches:
        header = "Related questions:" if result.is_answered else "You might mean:"
        lines = [spec.bold(header)] + [f"{spec.bullet} {spec.prepare(a.question)}"
                                       for a in result.alternative_matches[:spec.max_alternatives]]
        parts.append("\n".join(lines))
    body = "\n\n".join(parts)
    # truncate to spec.max_length if needed; compute sms_segments for SMS
    return FormattedReply(...)
```

One function, driven entirely by the channel's `spec`. The returned
`FormattedReply` also carries **metadata** — character count, segment count, whether
it was truncated — so the UI can show it for verification.[1]

> **Footnotes**
> [1] Returning metadata (not just the string) is what lets the chat window show
> "134 characters / 160 · 1 SMS segment(s)". Designing outputs to carry the
> information the *next* layer needs is a recurring theme in this codebase.

---

## Add a channel in three steps

Say you want **Slack** (bold is `*single*`, like WhatsApp):[1]

1. Add `SLACK = "slack"` to the `Channel` enum.
2. Add one `ChannelSpec` to the `CHANNELS` dict with Slack's rules.
3. List it in `ORDERED_CHANNELS` — it now appears in the sidebar automatically.

No UI or logic changes. That is the payoff of rules-as-data.

🛠️ **Try it:** in the app, ask a question, then switch **Reply format** in the
sidebar between Chat/WhatsApp/Telegram/SMS. The *same* answer reformats instantly —
because formatting happens at display time from the stored result.

> **Footnotes**
> [1] Add a matching test in `tests/test_formatting.py` to lock in the new channel's
> behavior. In V1 this layer *formats and previews*; actually sending (Telegram Bot
> API, an SMS gateway) is a future version — but `escape_markdown_v2` and the clean
> `format_reply` seam are already the right building blocks.

---

## Recap & what's next

- Each channel has **hard formatting rules**; one answer must be reshaped per
  channel.
- Rules live in a **`ChannelSpec`** (data, not conditionals); `format_reply` is one
  spec-driven function.
- **SMS** strips + segments; **Telegram** escapes MarkdownV2; adding a channel is a
  three-step, logic-free change.

**Next:** [Chapter 8 — The Streamlit UI](08-the-streamlit-ui.md): how the pages are
built, and the rerun model that makes Streamlit tick.
