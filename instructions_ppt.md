# How to Build a Code‑Walk‑Through Presentation (from scratch)

A reusable playbook for turning a codebase into a **beginner‑to‑mastery, slide‑style
walk‑through** that is *both* a readable Markdown reference *and* a polished HTML slide
deck — like the one in [`docs/walkthrough/`](docs/walkthrough/README.md).

It captures the structure, the design system, the build pipeline, the overflow
discipline, and the hard‑won gotchas, so you can reproduce this for any project.

---

## 1. The core idea: one source, two outputs

Write plain Markdown files that read top‑to‑bottom like a book, **and** render as slides
with [Marp](https://marp.app). One `---` horizontal rule = one slide. The *same* file is:

- a **document** on GitHub (scroll to read, links resolve), and
- a **deck** (`marp file.md` → HTML slides), published to GitHub Pages.

Keep the Markdown clean (no Marp front‑matter committed); the build **injects** the
front‑matter into temporary copies so GitHub rendering stays tidy.

---

## 2. Information architecture

```text
docs/walkthrough/
├── README.md                 ← landing page: learning path, how to read/present
├── 01-<topic>.md … NN-<topic>.md   ← one chapter per architectural layer
├── GLOSSARY.md               ← every term, defined plainly, linked from footnotes
└── assets/
    ├── marp-theme.css        ← the design system (see §4)
    └── architecture.svg      ← diagrams (self‑contained SVG)
```

**Order chapters by the data flow**, not by folder — trace what happens to one input as
it travels through the system. Understanding the flow is the fastest route to mastery.
End with a "put it all together" chapter (full end‑to‑end trace + exercises + a
self‑assessment).

---

## 3. Chapter & slide anatomy

Each chapter is a mini‑presentation. Per **chapter**:

- Title + one‑line hook; a **"By the end… you will be able to:"** objectives line.
- A `Files:` line linking the real source files the chapter covers.
- 5–9 **slides** separated by `---`.
- A **Recap** slide ending with a **Next:** link to the following chapter.

Per **slide** keep it to *one idea*:

- an `## H2` slide title,
- a short lead sentence,
- **bullets for the enumerable points** (keep prose only for connective logic — bullet
  *where apt*, don't fragment an argument that needs to be sentences),
- **one** short code excerpt (illustrative, trimmed),
- optionally a small table,
- a **Footnotes** block appended at the bottom (see below).

### Footnotes on every slide (the "citation layer")

Reference notes inline as `[1]`, `[2]`, and end the slide with a blockquote whose
**each reference is its own bullet** — scannable, and it flows to the full width:

```markdown
Main point with a nuance.[1]

> **Footnotes**
>
> - **[1]** Define the jargon, explain the *why*, note a pitfall, or point to further reading.
> - **[2]** …
```

Footnotes are where the depth lives. Style them as a **quiet, subordinate band** (§4) so
they never compete with the body. (A small script can convert `> [n] …` blocks to this
bulleted form in bulk — see `footnotes_to_bullets.py` in the commit history.)

### Authoring conventions that pay off

- **Label every code block with its file** — a header comment on the first line:
  ```python
  # app/database/repository.py
  class FAQRepository: ...
  ```
  For usage snippets: `# any caller — importing from app/config/settings.py`. For
  anti‑examples: `# ❌ anti-pattern — NOT in this project`. Never leave the reader guessing
  which file a snippet is from.
- **Callouts** as emoji‑prefixed bold lines: `🧠 **Nuance:**`, `⚠️ **Pitfall:**`,
  `🛠️ **Try it:**`. Minimal, scannable, no special CSS needed.
- **Define jargon in *bold italic*** (`***embedding***`) and mirror it in the glossary.
- **Cross‑link** chapters and link code to the real source files (`../../app/...`).
- Keep an **honest scope note** where V1 defers something (say what would change the call).

---

## 4. The design system (the theme)

The look is **minimal and functional**: one accent hue, a clear type scale, quiet
citations, contained code/tables, consistent rhythm. It lives in one file,
[`docs/walkthrough/assets/marp-theme.css`](docs/walkthrough/assets/marp-theme.css)
(`/* @theme walkthrough */`, `@import 'default';` then overrides).

**Principles**

| Element | Rule |
|--------|------|
| Slide size | **Taller than 16:9** (1280×940) → more vertical room for dense slides |
| Type scale (large‑room) | **h1 46 › h2 31 › body/li 21 › table 16.5 › code 14.5 › citations 15**px — sized to read from the back of a room; code/table only as small as they must be to fit |
| **Contrast (WCAG 2.2 AA)** | every text colour ≥ **4.5:1** on white (large text ≥3:1). Secondary greys darkened accordingly (a `#8a929c` label at 3.2:1 **fails** — use ≥`#5b6570`) |
| Title (h2) | bold + a **hairline underline** → a clear title layer |
| Accent | **one hue** (links, the h2 rule, list bullets, footnote `[n]` refs) |
| Citations | **top hairline** + tiny uppercase "FOOTNOTES" label; each reference is its **own bullet** with the `[n]` in the accent colour |
| Code | a **card**: subtle background + 1px border + radius; inline code as chips |
| Tables | clean header rule + subtle zebra striping |
| Placement | `justify-content: center` → balanced vertical rhythm |
| Safety | `overflow: hidden` on the section as a last resort |

**Big fonts + bulleting go together:** larger type costs vertical room; converting prose to
bullets (shorter lines, fewer words) *buys it back*. Do both, then measure. For an unusually
dense slide, a scoped `<!-- _class: dense -->` (smaller code + citations) is the escape hatch.

**Overflow discipline** — Marp slides are a *fixed* size, so dense content overflows the
white area. Defend against it:

1. Keep **code, table, and footnote fonts tight** (they're the tallest content).
2. **Measure, don't guess** (§6): assert `scrollHeight ≤ clientHeight` on every slide.
3. For a single unavoidably‑tall slide, use a **scoped escape hatch** (a per‑slide class)
   instead of shrinking every slide:
   ```markdown
   ## The architecture — text version
   <!-- _class: diagram-text -->     ← just this slide's code gets smaller
   ```
   ```css
   section.diagram-text pre { font-size: 12.5px; line-height: 1.34; }
   section.dense { font-size: 19px; }              /* whole-slide shrink */
   section.dense pre { font-size: 13px; }
   section.dense blockquote, section.dense blockquote li { font-size: 13.5px; }
   ```
4. **Don't shrink the slide toward 16:9** to fit more — the taller 1280×940 *is* the room.
   Reducing height steals the space the dense slides depend on.

---

## 5. The build pipeline

Two scripts render every chapter + a combined deck into self‑contained HTML:

- [`scripts/build_slides.ps1`](scripts/build_slides.ps1) (Windows) and
  [`scripts/build_slides.sh`](scripts/build_slides.sh) (macOS/Linux/CI).

```bash
./scripts/build_slides.sh            # HTML decks into build/slides/
./scripts/build_slides.sh --pdf      # also PDFs (needs Chromium)
MARP_CMD=marp ./scripts/build_slides.sh    # use an installed marp (CI does this)
```

What the scripts do, and **why**:

1. **Inject front‑matter** (`marp: true`, `theme: walkthrough`, `paginate`, `footer`) into a
   temp copy of each chapter — so the committed `.md` stays clean for GitHub.
2. Build each chapter **and** a concatenated `walkthrough-full.html`.
3. **Copy `assets/*.svg` next to the decks** — Marp does **not** inline `<img>` into HTML,
   so a relative `assets/architecture.svg` would 404 without this.
4. Pass `-c .marprc.yml --no-stdin --allow-local-files --theme assets/marp-theme.css`.
5. Clean up temp files in a `finally`/`trap`.

**Two Marp options that matter a lot** (in `.marprc.yml` / the CLI flags):

```yaml
# .marprc.yml
options:
  markdown:
    breaks: false     # single newlines are spaces, not <br>
```

- **`breaks: false`** — Marp's default is `breaks: true`, which turns every single newline in
  the source into a hard `<br>`. If (like here) you hard‑wrap Markdown at ~90 cols for readable
  diffs, the *slides* then wrap at that ~90‑col point, leaving a big empty gutter on the right
  and making footnotes "wrap too early". Setting `breaks: false` lets text flow to the full
  slide width and wrap naturally — and matches how GitHub already renders your `.md`.
- **`--no-stdin`** — Marp CLI blocks *waiting on stdin* when it isn't attached to a TTY
  (backgrounded builds, some CI). Always pass `--no-stdin` for file‑based builds or the build
  hangs forever.

---

## 6. Validate visually — without guessing

Two fast, reliable checks:

**Overflow (must be zero).** Serve the decks and measure every slide in the browser —
**after the page settles** (measure at first paint and web‑font/monospace metrics can
report a phantom ~20px overflow that clears on reflow):

```js
// run in the deck page's console (or via an automation tool), then re-run once
[...document.querySelectorAll('section')]
  .map((s,i) => ({ slide:i+1, vOver: s.scrollHeight - s.clientHeight }))
  .filter(x => x.vOver > 2);   // expect []  (also check pre/table horizontal overflow)
```

**Look at the pixels.** Render slides to PNG and inspect them — no flaky browser pane
(this is the *reliable* visual check; use the same config/flags as the build):

```bash
marp chapter.md --images png -c .marprc.yml --no-stdin \
  --allow-local-files --theme assets/marp-theme.css -o out/ch.png
# → out/ch.001.png, ch.002.png, … open/read them
```

Check the worst‑case slides: the densest code slide, the biggest table, and any
image/ASCII slide. Confirm the citation band reads as subordinate and nothing is clipped.

**Test dark mode.** If you pinned the deck light (§9), confirm it: emulate a dark OS theme
and check a slide's background stays white with dark text —
`getComputedStyle(document.querySelector('section')).backgroundColor` should be `rgb(255,255,255)`.

---

## 7. Publish to GitHub Pages (CI)

[`.github/workflows/pages.yml`](.github/workflows/pages.yml): on push, install Marp CLI,
run `build_slides.sh` (`MARP_CMD=marp`), generate a landing `index.html` linking to every
deck, and deploy with the official Pages actions.

Enable Pages **once** (the Actions token can't create the site):

```bash
gh api -X POST repos/<owner>/<repo>/pages -f build_type=workflow
```

Then every push rebuilds and republishes the decks automatically.

---

## 8. Step‑by‑step to start from scratch

1. Create `docs/walkthrough/` with `README.md`, `GLOSSARY.md`, and `assets/`.
2. Drop in the theme (`marp-theme.css`) and copy/adapt the two `build_slides` scripts.
3. Draft chapters **in data‑flow order**; one idea per slide; footnotes on each; label
   every code block with its file.
4. Build locally (`build_slides.sh`), then **validate**: overflow = 0 (§6) and eyeball the
   PNGs.
5. Wire the base `README.md` to the walk‑through landing page.
6. Add the Pages workflow, enable Pages once, push — done.

---

## 9. Gotchas worth remembering

- **Marp doesn't inline images into HTML** → copy assets next to the decks.
- **Marp doesn't auto‑fit content** → design compact + measure overflow + scoped escape
  hatch for one tall slide.
- **Windows PowerShell 5.1 reads BOM‑less files as ANSI** → read sources as UTF‑8 and keep
  the `.ps1` ASCII‑only, or em‑dashes become mojibake.
- **Native stderr can look "fatal" in PowerShell** (`ErrorActionPreference=Stop`) → judge
  Marp success by **exit code**, not stderr.
- **Don't run two builds concurrently** — they share temp files in `docs/walkthrough/` and
  will clobber each other ("Not found processable Markdown").
- **HTML comments (`<!-- _class: … -->`) are invisible** in both Marp and GitHub — safe for
  per‑slide directives.
- **Marp's `breaks: true` default** turns hard‑wrapped source into `<br>` → text wraps early
  with a right gutter. Set `breaks: false` (see §5).
- **Marp CLI hangs waiting on stdin** when not a TTY → always pass `--no-stdin`.
- **Imported `default` theme is dark‑mode‑aware** (`light-dark()` + `color-scheme`). If your
  overrides use fixed light‑mode colours, pin the deck light with `:root { color-scheme: light; }`
  (it inherits to `section`, so `light-dark()` stays light) — otherwise dark‑mode viewers get
  dark text on a dark slide.
- **First‑paint overflow is a phantom** — measure overflow *after* the page settles (fonts/
  monospace metrics finalise), or re‑run the check; the first read can show ~20px that clears.
- **The stage around a slide is `body { background: #000 }`** (Marp's default). A tall slide
  letterboxes, so light slides sit in a black frame. Optional: soften it with
  `html body { background: #d7dbe1 }` (specificity beats the template's `body{}`). Left black
  here because it's fine for full‑screen projection; change it for in‑browser reading.

---

*This playbook describes how the walk‑through in this repo was built. See
[`instructions.md`](instructions.md) for the project spec, and the live decks at the
[walk‑through landing page](docs/walkthrough/README.md).*
