#!/usr/bin/env bash
# Build the code walk-through chapters into HTML slide decks with Marp.
#
# Renders each numbered chapter in docs/walkthrough/ into a self-contained HTML
# slide deck, plus one combined deck. Source .md files are left untouched (no Marp
# front-matter committed, so they render cleanly on GitHub); this script injects
# the front-matter into temporary copies at build time.
#
# Requires Node.js (for `npx`). Marp CLI is fetched on first run via npx.
#
# Usage:
#   scripts/build_slides.sh            # HTML decks into build/slides/
#   scripts/build_slides.sh --pdf      # also export PDFs (needs Chromium/Chrome)
#   OUT_DIR=/tmp/decks scripts/build_slides.sh
set -euo pipefail

REPO_ROOT="$(cd "$(dirname "${BASH_SOURCE[0]}")/.." && pwd)"
WALK_DIR="$REPO_ROOT/docs/walkthrough"
OUT_DIR="${OUT_DIR:-$REPO_ROOT/build/slides}"
PDF=""
[ "${1:-}" = "--pdf" ] && PDF="1"

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

FRONT_MATTER=$'---\nmarp: true\ntheme: default\npaginate: true\nfooter: \'Semantic FAQ Chatbot - Code Walk-Through\'\n---\n\n'

# Collect numbered chapters (01-..10-) in order; README.md/GLOSSARY.md excluded.
mapfile -t CHAPTERS < <(find "$WALK_DIR" -maxdepth 1 -name '[0-9][0-9]-*.md' | sort)
if [ "${#CHAPTERS[@]}" -eq 0 ]; then
  echo "Error: no chapter files found in $WALK_DIR" >&2
  exit 1
fi

TEMP_FILES=()
cleanup() { for t in "${TEMP_FILES[@]:-}"; do [ -f "$t" ] && rm -f "$t"; done; }
trap cleanup EXIT

marp_build() { # $1 = input md, $2 = output path, $3 = optional --pdf
  # shellcheck disable=SC2086  # MARP_CMD is intentionally word-split (e.g. "npx --yes ...")
  $MARP_CMD "$1" -o "$2" --allow-local-files ${3:-}
}

# --- one deck per chapter ---
for ch in "${CHAPTERS[@]}"; do
  base="$(basename "$ch" .md)"
  tmp="$WALK_DIR/_build_${base}.md"
  TEMP_FILES+=("$tmp")
  printf '%s' "$FRONT_MATTER" > "$tmp"; cat "$ch" >> "$tmp"
  echo "Building $(basename "$ch") -> $OUT_DIR/${base}.html"
  marp_build "$tmp" "$OUT_DIR/${base}.html"
  [ -n "$PDF" ] && marp_build "$tmp" "$OUT_DIR/${base}.pdf" "--pdf"
done

# --- one combined deck ---
combined="$WALK_DIR/_build_walkthrough-full.md"
TEMP_FILES+=("$combined")
printf '%s' "$FRONT_MATTER" > "$combined"
first=1
for ch in "${CHAPTERS[@]}"; do
  [ "$first" -eq 1 ] || printf '\n\n---\n\n' >> "$combined"
  cat "$ch" >> "$combined"; first=0
done
echo "Building combined deck -> $OUT_DIR/walkthrough-full.html"
marp_build "$combined" "$OUT_DIR/walkthrough-full.html"
[ -n "$PDF" ] && marp_build "$combined" "$OUT_DIR/walkthrough-full.pdf" "--pdf"

echo ""
echo "Done. Open the decks in $OUT_DIR (e.g. walkthrough-full.html)."
