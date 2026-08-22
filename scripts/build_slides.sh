#!/usr/bin/env bash
# Build a Marp slide deck from a folder of Markdown chapters.
#
# GENERIC: point it at ANY folder of numbered `NN-*.md` chapters (a code
# walk-through, a design review, a talk, ...) via SRC_DIR. By default the decks
# are written to a `slides/` subfolder INSIDE that source folder, so the rendered
# slides sit right next to the Markdown they came from -- intuitive, self-
# describing context (e.g. docs/walkthrough/ -> docs/walkthrough/slides/).
#
# Renders each numbered chapter into a self-contained HTML slide deck, plus one
# combined deck. The source .md files are left untouched (no Marp front-matter
# committed, so they render cleanly on GitHub); this script injects the
# front-matter into temporary copies at build time.
#
# Requires Node.js (for `npx`). Marp CLI is fetched on first run via npx.
#
# Usage:
#   scripts/build_slides.sh                         # decks -> <SRC_DIR>/slides/
#   scripts/build_slides.sh --pdf                   # also export PDFs (needs Chromium/Chrome)
#   SRC_DIR=docs/design-review scripts/build_slides.sh   # build a DIFFERENT presentation
#   OUT_DIR=/tmp/decks scripts/build_slides.sh          # override the output folder
#   FOOTER='My Talk' COMBINED=talk-full scripts/build_slides.sh  # override footer / combined name
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"

# --- What to build (all overridable via env) ---------------------------------
SRC_REL="${SRC_DIR:-docs/walkthrough}"                # folder of NN-*.md chapters
case "$SRC_REL" in /*) SRC_DIR="$SRC_REL" ;; *) SRC_DIR="$REPO_ROOT/$SRC_REL" ;; esac
OUT_DIR="${OUT_DIR:-$SRC_DIR/slides}"                 # default: a slides/ subfolder in SRC_DIR
FOOTER="${FOOTER:-Semantic FAQ Chatbot - Code Walk-Through}"   # slide footer text
COMBINED="${COMBINED:-walkthrough-full}"              # basename of the all-chapters deck
THEME="${THEME:-$SRC_DIR/assets/marp-theme.css}"      # design system
CONFIG="${MARP_CONFIG:-$REPO_ROOT/.marprc.yml}"       # markdown options (e.g. breaks: false)
PDF=""
[ "${1:-}" = "--pdf" ] && PDF="1"

[ -d "$SRC_DIR" ] || { echo "Error: source folder not found: $SRC_DIR" >&2; exit 1; }

# The Marp command. Defaults to fetching Marp CLI on demand via npx; CI (or anyone
# with Marp installed) can set MARP_CMD=marp to use a preinstalled binary.
MARP_CMD="${MARP_CMD:-npx --yes @marp-team/marp-cli@latest}"

marp_bin="${MARP_CMD%% *}"
if ! command -v "$marp_bin" >/dev/null 2>&1; then
  echo "Error: '$marp_bin' not found. Install Node.js from https://nodejs.org (for npx)," >&2
  echo "       or install Marp CLI and set MARP_CMD=marp." >&2
  exit 1
fi

mkdir -p "$OUT_DIR"

# Marp keeps relative image paths in HTML (it does not inline them), so copy the
# images next to the decks: `assets/architecture.svg` then resolves from OUT_DIR.
if compgen -G "$SRC_DIR/assets/"'*.svg' > /dev/null 2>&1; then
  mkdir -p "$OUT_DIR/assets"
  cp "$SRC_DIR/assets/"*.svg "$OUT_DIR/assets/" 2>/dev/null || true
fi

FRONT_MATTER=$'---\nmarp: true\ntheme: walkthrough\npaginate: true\nfooter: \''"$FOOTER"$'\'\n---\n\n'

# Collect numbered chapters (01-..NN-) in order; README.md/GLOSSARY.md excluded.
mapfile -t CHAPTERS < <(find "$SRC_DIR" -maxdepth 1 -name '[0-9][0-9]-*.md' | sort)
if [ "${#CHAPTERS[@]}" -eq 0 ]; then
  echo "Error: no chapter files (NN-*.md) found in $SRC_DIR" >&2
  exit 1
fi

TEMP_FILES=()
cleanup() { for t in "${TEMP_FILES[@]:-}"; do [ -f "$t" ] && rm -f "$t"; done; }
trap cleanup EXIT

marp_build() { # $1 = input md, $2 = output path, $3 = optional --pdf
  # shellcheck disable=SC2086  # MARP_CMD is intentionally word-split (e.g. "npx --yes ...")
  $MARP_CMD "$1" -o "$2" -c "$CONFIG" --no-stdin --allow-local-files --theme "$THEME" ${3:-}
}

# --- one deck per chapter ---
for ch in "${CHAPTERS[@]}"; do
  base="$(basename "$ch" .md)"
  tmp="$SRC_DIR/_build_${base}.md"
  TEMP_FILES+=("$tmp")
  printf '%s' "$FRONT_MATTER" > "$tmp"; cat "$ch" >> "$tmp"
  echo "Building $(basename "$ch") -> $OUT_DIR/${base}.html"
  marp_build "$tmp" "$OUT_DIR/${base}.html"
  [ -n "$PDF" ] && marp_build "$tmp" "$OUT_DIR/${base}.pdf" "--pdf"
done

# --- one combined deck ---
combined="$SRC_DIR/_build_${COMBINED}.md"
TEMP_FILES+=("$combined")
printf '%s' "$FRONT_MATTER" > "$combined"
first=1
for ch in "${CHAPTERS[@]}"; do
  [ "$first" -eq 1 ] || printf '\n\n---\n\n' >> "$combined"
  cat "$ch" >> "$combined"; first=0
done
echo "Building combined deck -> $OUT_DIR/${COMBINED}.html"
marp_build "$combined" "$OUT_DIR/${COMBINED}.html"
[ -n "$PDF" ] && marp_build "$combined" "$OUT_DIR/${COMBINED}.pdf" "--pdf"

echo ""
echo "Done. Open the decks in $OUT_DIR (e.g. ${COMBINED}.html)."
