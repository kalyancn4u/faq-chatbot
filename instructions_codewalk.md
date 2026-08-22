# Code Walk‑Through Kit — a repo‑agnostic recipe

**Drop this into *any* code repository to produce, from its source, a beginner‑to‑mastery
*code walk‑through* that ships as three things at once:**

1. **Markdown docs** — chapters that read like a book on GitHub;
2. **HTML slide decks** — the same chapters rendered as a presentation with Marp;
3. **A live site** — the decks auto‑published to `https://<owner>.github.io/<repo>/`.

This file is a **complete kit**: the methodology *plus* the exact, finalized theme CSS,
build config, build script, CI workflow, and helper script — copy them in, adapt a few
strings, write your chapters, and push. (For the narrative rationale and the story of how
each detail was arrived at, see the companion `instructions_ppt.md`.)

Replace these placeholders throughout: `<PROJECT>` (display name), `<owner>` / `<repo>`
(GitHub slug). The conventional content folder is `docs/walkthrough/`.

---

## 0. Prerequisites

- **[Node.js](https://nodejs.org)** — for [Marp CLI](https://marp.app) (fetched via `npx`,
  or `npm i -g @marp-team/marp-cli`).
- **git** + a **public** GitHub repo; **[`gh` CLI](https://cli.github.com)** to enable Pages once.
- *Optional:* **Python 3** to run the footnote‑to‑bullets helper (§F) and a static server for QA.

---

## A. Methodology — writing the markdown artifacts

### A1. One source, two outputs
Write plain Markdown. `---` on its own line = a new slide. The committed `.md` stays
**clean** (no Marp front‑matter); the build injects front‑matter into *temporary* copies, so
GitHub renders the files as normal docs while Marp renders them as slides.

### A2. Information architecture
```text
docs/walkthrough/
├── README.md                 # landing page: learning path, how to read/present
├── 01-<topic>.md … NN-<topic>.md   # ONE chapter per architectural layer
├── GLOSSARY.md               # every term, defined plainly, linked from footnotes
└── assets/
    ├── marp-theme.css        # the design system (§B)
    └── *.svg                 # self-contained diagrams
```
**Order chapters by the data flow**, not by folder — trace what happens to one input as it
travels through the system. End with a "put it all together" chapter (full end‑to‑end trace +
extension exercises + a self‑assessment).

### A3. Chapter anatomy
- Title + a one‑line hook; a **"By the end … you will be able to:"** objectives line.
- A `Files:` line linking the real source files the chapter covers.
- **5–9 slides** separated by `---`.
- A **Recap** slide ending with a **Next:** link to the following chapter.

### A4. Slide anatomy — one idea per slide
- an `## H2` slide title;
- a short lead sentence;
- **bullets for the enumerable points** — bullet *where apt* for scanability, but keep prose
  for connective logic (don't fragment an argument that needs to be sentences);
- **one** short, trimmed code excerpt;
- optionally a small table;
- a **Footnotes** block at the bottom (A6).

### A5. Label every code block with its file (no ambiguity)
Put the path as a header comment on the first line:
````markdown
```python
# path/to/module.py
class Thing: ...
```
````
For usage snippets: `# any caller — importing from path/to/module.py`. For anti‑examples:
`# ❌ anti-pattern — NOT in this project`.

### A6. Footnotes = the citation layer (each reference a bullet)
Reference inline as `[1]`, `[2]`; end the slide with a blockquote whose **each reference is its
own bullet** (flows to full width, scannable):
```markdown
Main point with a nuance.[1]

> **Footnotes**
>
> - **[1]** Define the jargon, explain the *why*, note a pitfall, or link further reading.
> - **[2]** …
```
Footnotes are where the depth lives; the theme renders them as a quiet, subordinate band.
Bulk‑convert legacy `> [n] …` blocks with the script in **§F**.

### A7. Other conventions
- **Callouts** as emoji‑bold lines: `🧠 **Nuance:**`, `⚠️ **Pitfall:**`, `🛠️ **Try it:**`.
- **Define jargon in *bold italic*** (`***term***`) and mirror it in the glossary.
- **Cross‑link** chapters and link code to the real source files (`../../<path>`).
- Add an **honest scope note** wherever the project defers something (say what would change
  the decision).

---

## B. The design system (the theme) — save as `docs/walkthrough/assets/marp-theme.css`

Principles, all embodied in the CSS below:

| Element | Rule |
|---|---|
| Slide size | **Taller than 16:9** (`1280×940`) → vertical room for dense slides. **Don't** shrink toward 16:9 to fit more — that steals the room the dense slides need. |
| Type scale (large room) | **h1 46 › h2 31 › body/li 21 › table 16.5 › code 14.5 › citations 15**px — legible from the back of an auditorium; code/table only as small as they must be. |
| **Contrast — WCAG 2.2 AA** | every text colour **≥ 4.5:1** on white (large text ≥3:1). A `#8a929c` label is only ~3.2:1 → **fails**; secondary greys use **≥ `#5b6570`** (~5.7:1). |
| Title (h2) | bold + a **hairline underline** → a clear title layer. |
| Accent | **one hue** only: links, the h2 rule, list bullets, footnote `[n]` refs. |
| Citations | **top hairline** + tiny uppercase "FOOTNOTES" label; each reference a bullet with `[n]` in the accent. |
| Code | a **card** (subtle bg + 1px border + radius); inline code as chips. |
| Tables | clean header rule + subtle zebra. |
| Placement | `justify-content: center` for balanced vertical rhythm; `overflow: hidden` as a last‑resort safety net. |
| **Light‑pinned** | `:root { color-scheme: light }` — the imported `default` theme is dark‑mode‑aware via `light-dark()`; without the pin, dark‑mode viewers get our fixed dark text on a dark slide. |

```css
/* @theme walkthrough */   /* the name here must match `theme: walkthrough` in the build */

@import 'default';

:root {
  color-scheme: light;   /* pin light so the imported theme's light-dark() tokens
                            never flip our fixed dark text onto a dark slide. */
  --ink:    #1f2328;   /* primary text — 15:1 on white                */
  --muted:  #565d66;   /* citation body — ~5.8:1 on white             */
  --faint:  #5b6570;   /* labels / markers / footer — ~5.7:1 (WCAG AA) */
  --accent: #3b5bdb;   /* single accent hue — ~5.7:1                   */
  --rule:   #d7dbe0;   /* hairlines                                    */
  --rule-2: #c3c9d0;   /* stronger hairline                            */
  --code-bg:#f6f8fa;   /* code / zebra background                      */
}

/* ---------- Slide surface ---------- */
section {
  width: 1280px;
  height: 940px;               /* taller than 16:9 -> more vertical room */
  padding: 44px 60px;
  font-size: 21px;             /* body baseline — legible in a room */
  line-height: 1.5;
  color: var(--ink);
  justify-content: center;
  overflow: hidden;            /* final safety net */
}

/* ---------- Headings ---------- */
h1 { font-size: 46px; font-weight: 700; letter-spacing: -0.5px; margin: 0 0 .26em; }
h2 {                            /* slide title */
  font-size: 31px; font-weight: 700; letter-spacing: -0.3px;
  margin: 0 0 .55em; padding-bottom: .24em;
  border-bottom: 2px solid var(--rule-2);
}
h3 { font-size: 21px; font-weight: 600; color: var(--muted); margin: .7em 0 .25em; }

/* ---------- Body ---------- */
p  { margin: .4em 0; }
ul, ol { margin: .35em 0 .45em 1.1em; padding-left: .35em; }
li { margin: .28em 0; }
li::marker { color: var(--accent); }        /* accent bullets tie the deck together */
strong { font-weight: 700; }
em { color: inherit; }
a { color: var(--accent); text-decoration: none; border-bottom: 1px solid rgba(59, 91, 219, .3); }

/* ---------- Inline & block code ---------- */
:not(pre) > code {
  font-size: 0.9em; background: var(--code-bg);
  border: 1px solid var(--rule); border-radius: 5px; padding: .04em .34em;
}
pre {
  font-size: 14.5px; line-height: 1.45; margin: .5em 0; padding: .6em .85em;
  background: var(--code-bg); border: 1px solid var(--rule); border-radius: 8px;
  overflow-x: auto;
}
pre code { font-size: inherit; background: none; border: none; padding: 0; }

/* Scoped escape hatches (apply per slide with an HTML comment, e.g. <!-- _class: dense -->) */
section.diagram-text pre { font-size: 12.5px; line-height: 1.34; }   /* one tall block */
section.dense { font-size: 19px; }                                    /* whole slide */
section.dense pre { font-size: 13px; }
section.dense blockquote, section.dense blockquote li { font-size: 13.5px; }

/* ---------- Tables ---------- */
table { font-size: 16.5px; border-collapse: collapse; margin: .5em 0; }
th, td { padding: 6px 13px; text-align: left; border-bottom: 1px solid var(--rule); }
thead th { border-bottom: 2px solid var(--rule-2); font-weight: 700; }
tbody tr:nth-child(even) { background: rgba(27, 31, 36, .025); }

/* ---------- Citations (the "> Footnotes" blockquote) ---------- */
blockquote {
  margin: .85em 0 0; padding: .45em 0 0; border: 0;
  border-top: 1px solid var(--rule);   /* subordinate band, separated by a hairline */
  color: var(--muted); font-size: 15px; line-height: 1.4;
}
blockquote > p { margin: 0 0 .15em; }                     /* the "FOOTNOTES" label line */
blockquote > p strong {                                    /* the label ONLY, not [n] refs */
  color: var(--faint); font-weight: 700; text-transform: uppercase;
  letter-spacing: .7px; font-size: 12.5px;
}
blockquote ul { margin: .1em 0 0 1.15em; padding-left: .3em; list-style: disc; }
blockquote li { font-size: 15px; margin: .16em 0; color: var(--muted); }
blockquote li::marker { color: var(--faint); font-size: .85em; }
blockquote li strong { color: var(--accent); font-weight: 700; }   /* the [n] reference */
blockquote code { font-size: .95em; background: rgba(27, 31, 36, .05); border-color: transparent; }
blockquote a { color: var(--accent); }

/* ---------- Media ---------- */
img { max-width: 100%; max-height: 500px; height: auto; }

/* ---------- Chrome: footer + pagination ---------- */
footer { font-size: 13px; color: var(--faint); opacity: 1; }
section::after { font-size: 14px; color: var(--faint); }
```

> **Optional — the stage colour.** Marp's player frames slides in `body { background: #000 }`,
> so a tall (letterboxed) slide sits in a black surround. Fine for full‑screen projection; for
> in‑browser reading you may prefer a soft grey — add `html body { background: #d7dbe1 }`
> (its specificity beats the template's `body{}`).

---

## C. Build config & script

### C1. `.marprc.yml` (repo root) — **two options that matter a lot**
```yaml
options:
  markdown:
    breaks: false     # single newlines are spaces, not <br>
```
- **`breaks: false`** — Marp's default (`true`) turns every single newline in the source into a
  hard `<br>`. If you hard‑wrap Markdown at ~90 cols for clean diffs, the *slides* then wrap at
  ~90 cols with a big right gutter (footnotes "wrap too early"). `false` lets text flow to the
  full slide width — and matches how GitHub already renders your `.md`.
- Also always pass **`--no-stdin`** on the CLI (below) — Marp *hangs waiting on stdin* when not
  attached to a TTY (backgrounded builds, some CI).

### C2. `scripts/build_slides.sh` (macOS / Linux / CI)
Renders each chapter **and** a combined deck to self‑contained HTML. It is **generic**: the
source folder is a parameter (`SRC_DIR`), so the *same* script builds any presentation from its
own chapter folder — the content comes from whichever Markdown folder you point it at. By default
the decks are written to a **`slides/` subfolder inside that source folder** (e.g.
`docs/walkthrough/` → `docs/walkthrough/slides/`), so the rendered slides sit **right next to the
Markdown they came from** rather than in a detached top‑level `build/`. Everything else —
`OUT_DIR`, the `FOOTER` string, the combined‑deck name — is overridable too; no per‑repo editing
of the script is needed.
```bash
#!/usr/bin/env bash
# Build a Marp slide deck from a folder of Markdown chapters. GENERIC over SRC_DIR.
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# What to build (all overridable via env):
SRC_REL="${SRC_DIR:-docs/walkthrough}"                # folder of NN-*.md chapters
case "$SRC_REL" in /*) SRC_DIR="$SRC_REL" ;; *) SRC_DIR="$REPO_ROOT/$SRC_REL" ;; esac
OUT_DIR="${OUT_DIR:-$SRC_DIR/slides}"                 # default: slides/ INSIDE the source folder
FOOTER="${FOOTER:-<PROJECT> — Code Walk-Through}"     # slide footer text
COMBINED="${COMBINED:-walkthrough-full}"              # basename of the all-chapters deck
THEME="${THEME:-$SRC_DIR/assets/marp-theme.css}"
CONFIG="${MARP_CONFIG:-$REPO_ROOT/.marprc.yml}"
PDF=""
[ "${1:-}" = "--pdf" ] && PDF="1"
[ -d "$SRC_DIR" ] || { echo "Source folder not found: $SRC_DIR" >&2; exit 1; }

# Default to npx; CI (or anyone with Marp installed) sets MARP_CMD=marp.
MARP_CMD="${MARP_CMD:-npx --yes @marp-team/marp-cli@latest}"
marp_bin="${MARP_CMD%% *}"
command -v "$marp_bin" >/dev/null 2>&1 || { echo "Install Node.js, or set MARP_CMD=marp" >&2; exit 1; }

mkdir -p "$OUT_DIR"
# Marp keeps relative <img> paths (it does NOT inline them) -> copy assets next to the decks.
if compgen -G "$SRC_DIR/assets/"'*.svg' > /dev/null 2>&1; then
  mkdir -p "$OUT_DIR/assets"; cp "$SRC_DIR/assets/"*.svg "$OUT_DIR/assets/" 2>/dev/null || true
fi

FRONT_MATTER=$'---\nmarp: true\ntheme: walkthrough\npaginate: true\nfooter: \''"$FOOTER"$'\'\n---\n\n'

mapfile -t CHAPTERS < <(find "$SRC_DIR" -maxdepth 1 -name '[0-9][0-9]-*.md' | sort)
[ "${#CHAPTERS[@]}" -gt 0 ] || { echo "No chapters (NN-*.md) in $SRC_DIR" >&2; exit 1; }

TEMP_FILES=()
cleanup() { for t in "${TEMP_FILES[@]:-}"; do [ -f "$t" ] && rm -f "$t"; done; }
trap cleanup EXIT

marp_build() {  # $1 in.md  $2 out  $3 optional --pdf
  # shellcheck disable=SC2086
  $MARP_CMD "$1" -o "$2" -c "$CONFIG" --no-stdin --allow-local-files --theme "$THEME" ${3:-}
}

# one deck per chapter
for ch in "${CHAPTERS[@]}"; do
  base="$(basename "$ch" .md)"; tmp="$SRC_DIR/_build_${base}.md"; TEMP_FILES+=("$tmp")
  printf '%s' "$FRONT_MATTER" > "$tmp"; cat "$ch" >> "$tmp"
  echo "Building $(basename "$ch")"; marp_build "$tmp" "$OUT_DIR/${base}.html"
  [ -n "$PDF" ] && marp_build "$tmp" "$OUT_DIR/${base}.pdf" "--pdf"
done

# one combined deck
combined="$SRC_DIR/_build_${COMBINED}.md"; TEMP_FILES+=("$combined")
printf '%s' "$FRONT_MATTER" > "$combined"; first=1
for ch in "${CHAPTERS[@]}"; do
  [ "$first" -eq 1 ] || printf '\n\n---\n\n' >> "$combined"; cat "$ch" >> "$combined"; first=0
done
marp_build "$combined" "$OUT_DIR/${COMBINED}.html"
[ -n "$PDF" ] && marp_build "$combined" "$OUT_DIR/${COMBINED}.pdf" "--pdf"
echo "Done -> $OUT_DIR (open ${COMBINED}.html)"
```
Run `./scripts/build_slides.sh` (→ `docs/walkthrough/slides/`). Add `--pdf` for PDFs, or
`MARP_CMD=marp` to use an installed binary. Build a **different** presentation without editing the
script: `SRC_DIR=docs/design-review FOOTER='Design Review' COMBINED=review-full ./scripts/build_slides.sh`.

**Git‑ignore the derived decks** — since the output now lives under your tracked docs tree, add
`docs/**/slides/` and `docs/**/_build_*.md` to `.gitignore` so built decks and temp files are
never committed.

### C3. Windows (`scripts/build_slides.ps1`)
Mirror the bash logic (same `-SrcDir` / `-OutDir` / `-Footer` / `-Combined` parameters, same
default of `<SrcDir>/slides`) with two Windows‑specific rules: **read sources as UTF‑8 and keep
the `.ps1` ASCII‑only** (PowerShell 5.1 reads BOM‑less files as ANSI → em‑dashes become mojibake),
and **judge Marp success by exit code, not stderr** (with `$ErrorActionPreference='Stop'`, a
native command's stderr looks fatal). Pass the same flags: `-c .marprc.yml --no-stdin
--allow-local-files --theme <theme>`. Run: `./scripts/build_slides.ps1` (add `-Pdf` for PDFs;
`-SrcDir docs/design-review -Footer 'Design Review' -Combined review-full` for a different deck).

---

## D. Validate — don't guess

- **Overflow must be zero.** Serve `docs/walkthrough/slides/` and, in the deck's console, measure **after
  the page settles** (first paint can report a phantom ~20px that clears on reflow — re‑run):
  ```js
  [...document.querySelectorAll('section')]
    .map((s,i)=>({slide:i+1, vOver: s.scrollHeight - s.clientHeight}))
    .filter(x => x.vOver > 2);   // expect []  (also check pre/table horizontal overflow)
  ```
- **Look at the pixels** (the reliable check — no flaky browser needed). Render to PNG with the
  **same flags** and open them:
  ```bash
  marp docs/walkthrough/01-*.md --images png -c .marprc.yml --no-stdin \
    --allow-local-files --theme docs/walkthrough/assets/marp-theme.css -o /tmp/png/ch.png
  ```
  Check the worst cases: densest code slide, biggest table, any image/ASCII slide.
- **Test the light‑pin.** Emulate a dark OS theme; a slide's background must stay white:
  `getComputedStyle(document.querySelector('section')).backgroundColor === 'rgb(255, 255, 255)'`.

---

## E. Publish to `https://<owner>.github.io/<repo>/`

### E1. Workflow — `.github/workflows/pages.yml`
Builds on push, generates a landing `index.html` linking every deck, and deploys with the
official Pages actions. Replace `<PROJECT>` and the GitHub URL.
```yaml
name: Publish Walk-Through Slides
on:
  push:
    branches: [main]
    paths: ["docs/walkthrough/**", "scripts/build_slides.sh", ".github/workflows/pages.yml"]
  workflow_dispatch: {}
permissions: { contents: read, pages: write, id-token: write }
concurrency: { group: pages, cancel-in-progress: true }
jobs:
  build:
    runs-on: ubuntu-latest
    steps:
      - uses: actions/checkout@v4
      - uses: actions/setup-node@v4
        with: { node-version: 20 }
      - uses: actions/configure-pages@v5
      - run: npm install -g @marp-team/marp-cli@latest
      - name: Build slide decks
        # Redirect OUT_DIR into the Pages artifact; the deployed URL stays
        # https://<owner>.github.io/<repo>/slides/... regardless of the local default.
        env: { MARP_CMD: marp, SRC_DIR: docs/walkthrough, OUT_DIR: ${{ github.workspace }}/_site/slides }
        run: bash scripts/build_slides.sh
      - name: Generate landing page
        run: |
          slides_dir="_site/slides"; index="_site/index.html"
          {
            echo '<!doctype html><html lang="en"><head><meta charset="utf-8">'
            echo '<meta name="viewport" content="width=device-width, initial-scale=1">'
            echo '<title><PROJECT> — Code Walk-Through</title>'
            echo '<style>body{font-family:-apple-system,Segoe UI,Roboto,Arial,sans-serif;max-width:760px;margin:3rem auto;padding:0 1rem;line-height:1.6;color:#1f2328}a{color:#0969da;text-decoration:none}a:hover{text-decoration:underline}.hero{padding:1rem 1.25rem;border:1px solid #d0d7de;border-radius:12px;background:#f6f8fa}@media(prefers-color-scheme:dark){body{background:#0d1117;color:#e6edf3}.hero{background:#161b22;border-color:#30363d}a{color:#58a6ff}}</style>'
            echo '</head><body><h1><PROJECT> — Code Walk-Through</h1>'
            echo '<p class="hero">▶ <strong><a href="slides/walkthrough-full.html">Open the full deck</a></strong></p>'
            echo '<h2>Chapters</h2><ul>'
            for f in "$slides_dir"/[0-9][0-9]-*.html; do
              base="$(basename "$f" .html)"; num="${base%%-*}"; title="$(echo "${base#*-}" | tr '-' ' ')"
              echo "<li><a href=\"slides/${base}.html\">Chapter ${num#0} — ${title}</a></li>"
            done
            echo '</ul></body></html>'
          } > "$index"
      - uses: actions/upload-pages-artifact@v3
        with: { path: _site }
  deploy:
    needs: build
    runs-on: ubuntu-latest
    environment: { name: github-pages, url: "${{ steps.deployment.outputs.page_url }}" }
    steps:
      - id: deployment
        uses: actions/deploy-pages@v4
```

### E2. Enable Pages once (the Actions token can't create the site)
```bash
gh api -X POST repos/<owner>/<repo>/pages -f build_type=workflow
```
(Or: repo **Settings → Pages → Source: "GitHub Actions"**.) Then every push rebuilds and
republishes automatically. Note: `configure-pages@5` with `enablement: true` **fails** with
"Resource not accessible by integration" — the default token can't create Pages; enable it once
with your own `gh` credentials as above. The site is a **project page** at
`https://<owner>.github.io/<repo>/`; the repo must be public (or Pages‑enabled on your plan).

---

## F. Helper — bulk‑convert footnotes to bullets (`footnotes_to_bullets.py`)
Idempotent‑ish; only touches blockquotes whose first line is `**Footnotes**`. Joins hard‑wrapped
continuation lines and emits `> - **[n]** …`.
```python
import re, glob, os
REF = re.compile(r'^\[(\d+)\]\s*(.*)$')
def transform(lines):
    content = [ln[2:] if ln.startswith('> ') else ('' if ln == '>' else None) for ln in lines]
    if None in content: return None
    idx = next((i for i,c in enumerate(content) if c.strip()), None)
    if idx is None or content[idx].strip() != '**Footnotes**': return None
    entries, cur, pre = [], None, []
    for c in content[idx+1:]:
        s = c.strip()
        if not s: continue
        m = REF.match(s)
        if m:
            if cur is not None: entries.append(cur)
            cur = f'**[{m.group(1)}]** {m.group(2)}'.rstrip()
        elif cur is None:
            pre.append(s)                       # note text before any [n]
        else:
            cur = (cur + ' ' + s).strip()       # continuation of current [n]
    if cur is not None: entries.append(cur)
    out = ['> **Footnotes**', '>']
    if pre: out.append('> - ' + ' '.join(pre))
    out += ['> - ' + e for e in entries]
    return out
def process(path):
    lines = open(path, encoding='utf-8').read().split('\n'); out=[]; i=0; n=0
    while i < len(lines):
        if lines[i].startswith('>'):
            j=i
            while j < len(lines) and lines[j].startswith('>'): j+=1
            repl = transform(lines[i:j])
            out.extend(repl if repl else lines[i:j]); n += 1 if repl else 0; i=j
        else: out.append(lines[i]); i+=1
    if n: open(path,'w',encoding='utf-8').write('\n'.join(out))
    return n
for p in sorted(glob.glob('docs/walkthrough/[0-9][0-9]-*.md')):
    print(p, process(p))
```

---

## G. Quickstart — do this in order
1. Add `docs/walkthrough/` with `README.md`, `GLOSSARY.md`, `assets/marp-theme.css` (§B), plus
   `.marprc.yml` (§C1) and `scripts/build_slides.sh` (§C2).
2. Draft chapters **in data‑flow order**; one idea per slide; footnotes on each; label every
   code block with its file; bullet where apt.
3. Build locally: `./scripts/build_slides.sh` → open `docs/walkthrough/slides/walkthrough-full.html`.
4. **Validate** (§D): overflow = 0 (measure after settle) and eyeball the PNGs; test the light‑pin.
5. Wire your top‑level **`README.md`** to the walk‑through landing page (and this kit).
6. Add `.github/workflows/pages.yml` (§E1), enable Pages once (§E2), push. Visit
   `https://<owner>.github.io/<repo>/`.

---

## H. Gotchas (all learned the hard way)
- **Marp doesn't inline `<img>` into HTML** → copy `assets/*` next to the decks (the script does).
- **Marp doesn't auto‑fit content** → design compact, measure overflow, use a scoped `_class` hatch for one tall slide.
- **`breaks: true` (default)** turns hard‑wrapped source into `<br>` → early wraps + right gutter. Set `breaks: false`.
- **Marp CLI hangs on stdin** when not a TTY → always pass `--no-stdin`.
- **PowerShell 5.1**: reads BOM‑less files as ANSI (read UTF‑8, keep `.ps1` ASCII‑only); native stderr looks fatal under `Stop` (judge by exit code).
- **Don't run two builds at once** — they share temp files in the content dir and clobber each other.
- **`<!-- _class: … -->` comments are invisible** in Marp *and* GitHub — safe per‑slide directives.
- **Dark mode**: the imported `default` theme flips via `light-dark()`; pin `:root{color-scheme:light}` or dark‑mode viewers get dark‑on‑dark.
- **First‑paint overflow is a phantom** — re‑measure after the page settles.
- **Pages enablement**: the CI token can't create the site; enable once via `gh api … build_type=workflow`.
- **Contrast**: never ship secondary greys below 4.5:1 on white (large text 3:1) — WCAG 2.2 AA.

---

## Appendix — file manifest
| File | Purpose |
|---|---|
| `docs/walkthrough/*.md` | chapters (markdown docs) |
| `docs/walkthrough/README.md`, `GLOSSARY.md` | landing page + glossary |
| `docs/walkthrough/assets/marp-theme.css` | the design system (§B) |
| `docs/walkthrough/assets/*.svg` | self‑contained diagrams |
| `.marprc.yml` | Marp options (`breaks: false`) |
| `scripts/build_slides.sh` / `.ps1` | build the HTML/PDF decks |
| `.github/workflows/pages.yml` | build + publish to GitHub Pages |

*Companion docs: `instructions_ppt.md` (the narrated version of this recipe) and, for the
example repo this kit was distilled from, `docs/walkthrough/`.*
