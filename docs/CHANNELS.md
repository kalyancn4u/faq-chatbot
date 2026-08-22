# Reply Formats (Channels) — A Complete Beginner's Guide

This guide explains, from zero, how the chatbot tailors its reply for different
places a message can be sent — **Chat window, WhatsApp, Telegram, and SMS** — how
to try each one, and how to add your own. No prior knowledge is assumed. Read it
top to bottom once and you will understand the whole feature.

---

## 1. Why do we need this at all?

A chatbot has *one* answer to give. But **where** that answer is delivered changes
**how** it must be written. The same sentence that looks great in a web chat can
look broken — or be outright rejected — on another channel.

Three things differ from channel to channel:

1. **How you make text bold.** Web chat uses `**two asterisks**`. WhatsApp uses
   `*one asterisk*`. SMS has no bold at all.
2. **Whether emoji work.** Chat/WhatsApp/Telegram show emoji fine. Classic SMS
   cannot — an emoji becomes mojibake or is dropped.
3. **How long a message may be.** A web chat is effectively unlimited. WhatsApp
   and Telegram allow ~4096 characters. **SMS is billed in 160-character
   "segments"** — go one character over and it costs two messages.

Telegram adds a fourth wrinkle: it uses a strict format called **MarkdownV2** in
which ordinary punctuation like `.`, `-`, `(`, `)`, `!`, `>` **must be
"escaped"** (prefixed with a backslash `\`) or the Telegram server refuses to
send the message.

If we ignored these rules, a WhatsApp reply might show literal `**` around words,
an SMS might arrive truncated mid-word and cost double, and a Telegram send would
simply fail. So we translate the one answer into the correct shape for each
channel. That translation is this feature.

---

## 2. The mental model

```text
        one answer                       one string, shaped for the channel
   (from the FAQ database)                (ready to display or send)

  ┌────────────────────┐   choose a    ┌──────────────────────────────┐
  │   AnswerResult      │──channel────▶ │   response_formatter          │──▶ "…"
  │  answer, confidence │               │  applies that channel's rules │
  │  related questions  │               └──────────────────────────────┘
  └────────────────────┘
```

- The **answer** is decided elsewhere (the search + confidence logic). That part
  does not change.
- The **formatter** only decides *how to write it down* for a chosen channel.

Keeping these two jobs separate is the whole point: you can add a new channel
without touching how answers are found, and later you could even *send* to
WhatsApp/Telegram from the same seam.

The code lives in one file: [`app/services/response_formatter.py`](../app/services/response_formatter.py).

---

## 3. The four channels, side by side

| Channel | Bold syntax | Emoji | Length limit | Confidence line | Related list | Special rule |
|--------|-------------|-------|--------------|-----------------|--------------|--------------|
| **Chat window** | `**bold**` | ✅ | none | ✅ | ✅ | full Markdown |
| **WhatsApp** | `*bold*` | ✅ | ~4096 | ✅ | ✅ | single-asterisk bold |
| **Telegram** | `*bold*` | ✅ | ~4096 | ✅ | ✅ | escape `. - ( ) ! >` etc. |
| **SMS** | *(none)* | ❌ stripped | **160 / segment** | ❌ dropped | ❌ dropped | plain text only |

**Why SMS drops the confidence line and related questions:** every character
costs money in segments. On SMS the kindest reply is the answer itself and
nothing more.

### What the *same* answer looks like on each channel

Answer text: *"Refunds can be requested … from Settings > Billing > Order History.
Approved refunds take 5-10 business days."*

**Chat window** (rich Markdown, rendered):
> Refunds can be requested … from Settings > Billing > Order History. Approved
> refunds take 5-10 business days.
> **Confidence:** High
> **Related questions:** …

**WhatsApp** (note the single asterisks and `•` bullets):
```text
Refunds can be requested … from Settings > Billing > Order History. Approved refunds take 5-10 business days.

*Confidence:* High

*Related questions:*
• How do I contact customer support?
• How do I return an item?
```

**Telegram** (note the backslashes — required by MarkdownV2):
```text
Refunds can be requested … from Settings \> Billing \> Order History\. Approved refunds take 5\-10 business days\.

*Confidence:* High
```
The backslashes are **not** shown to the reader — Telegram uses them to know the
`>`, `.` and `-` are ordinary text, then renders clean prose. Without them the
send fails.

**SMS** (plain, trimmed, and measured):
```text
Refunds can be requested … from Settings > Billing > Order History. Approved refunds take 5-10 business days.
```
`134 characters / 160 limit · 1 SMS segment(s)` — fits in one segment. A longer
answer is truncated to 160 with a trailing `...`, and the app tells you how many
segments it *would* have taken.

---

## 4. How to try it (step by step)

1. Start the app:
   ```bash
   streamlit run app/main.py
   ```
2. In the **sidebar**, find **"Reply format"** and leave it on **Chat window**.
3. In the chat box at the bottom, type a question and press the send arrow, e.g.
   `how do I get a refund`. You'll see the normal rich answer.
4. Now change **"Reply format"** to **WhatsApp**. The *same* answer instantly
   re-renders in a monospace box showing exactly what WhatsApp would receive —
   `*Confidence:*`, `•` bullets, and a character count.
5. Switch to **Telegram**: watch the punctuation gain backslashes (`\.`, `\-`,
   `\>`). That's valid MarkdownV2.
6. Switch to **SMS**: the confidence and related lines disappear, and you get a
   `characters / 160 · N segment(s)` readout. Ask a very long question's FAQ to
   see truncation with `...`.

> **Why switching is instant:** the app stores the raw answer and formats it *at
> display time*. Change the channel and every message in the conversation
> re-formats at once — a fast way to confirm all four work.

**Developer mode** (also in the sidebar) adds a diagnostics panel under each
reply — matched FAQ id, similarity score, and the alternatives table — handy when
you want to see *why* a certain answer came back.

---

## 5. How it works in code (for when you're ready)

Everything is driven by a small **`ChannelSpec`** — one per channel — that records
that channel's rules:

```python
ChannelSpec(
    channel=Channel.WHATSAPP,
    label="WhatsApp",
    prepare=_identity,            # how to clean literal text (identity = leave as-is)
    bold=lambda s: f"*{s}*",      # how to make a label bold
    bullet="•",                   # bullet character for lists
    max_length=4096,              # truncate beyond this
    include_confidence=True,      # show the "Confidence:" line?
    include_alternatives=True,    # show "Related questions:"?
    max_alternatives=3,
)
```

`format_reply(result, channel)` then does the same four steps for every channel:

1. **Sanitize** the answer with the channel's `prepare` (SMS strips emoji +
   markdown; Telegram escapes MarkdownV2; chat/WhatsApp leave it alone).
2. **Optionally add** a bold `Confidence:` line and a bulleted related list.
3. **Join** the parts.
4. **Truncate** to `max_length` if needed, and for SMS compute the segment count.

Because the rules are *data* in a `ChannelSpec`, the logic in `format_reply`
never grows when you add a channel.

### The three text helpers (each is a plain function you can read in seconds)

- `strip_emoji(text)` — removes emoji/pictographs (SMS).
- `strip_markdown(text)` — turns `**bold**`, `[label](url)`, headings and bullets
  into plain text (SMS).
- `escape_markdown_v2(text)` — backslash-escapes Telegram's reserved characters.
  This is also the function you'd call before sending to the real Telegram Bot
  API with `parse_mode="MarkdownV2"`.

---

## 6. Add your own channel in 3 steps

Say you want a **"Slack"** channel (Slack bold is also single `*asterisks*`):

1. **Add the enum value** in `response_formatter.py`:
   ```python
   class Channel(str, Enum):
       ...
       SLACK = "slack"
   ```
2. **Add one `ChannelSpec`** to the `CHANNELS` dict:
   ```python
   Channel.SLACK: ChannelSpec(
       channel=Channel.SLACK, label="Slack",
       prepare=_identity, bold=lambda s: f"*{s}*", bullet="•",
       max_length=4000, include_confidence=True,
       include_alternatives=True, max_alternatives=3,
   ),
   ```
3. **List it** in `ORDERED_CHANNELS`. It now appears in the sidebar automatically.

That's it — no UI or logic changes. (Add a test in
[`tests/test_formatting.py`](../tests/test_formatting.py) to lock in the behavior.)

---

## 7. Important honesty about scope

In **Version 1 this is a formatter and previewer**, not a sender. It shows you
*exactly* what each channel would receive, which is what you need to design and
verify replies. Actually delivering messages (WhatsApp Business API, Telegram Bot
API, an SMS gateway like Twilio) is deliberately left for a later version — but
the `escape_markdown_v2` helper and the clean `format_reply` seam are already the
right building blocks for it.

---

## 8. Quick reference

- **Change channel:** sidebar → *Reply format*.
- **See diagnostics:** sidebar → *Developer mode*.
- **Bold:** chat `**x**`, WhatsApp/Telegram `*x*`, SMS none.
- **Emoji:** everywhere except SMS.
- **Limits:** chat none, WhatsApp/Telegram ~4096, SMS 160/segment.
- **Telegram:** punctuation is backslash-escaped (MarkdownV2) — that's correct.
- **Code:** `app/services/response_formatter.py` · **Tests:** `tests/test_formatting.py`.
