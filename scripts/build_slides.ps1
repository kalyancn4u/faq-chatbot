<#
.SYNOPSIS
    Build a Marp slide deck from a folder of Markdown chapters.

.DESCRIPTION
    Generic: point it at ANY folder of numbered `NN-*.md` chapters (a code
    walk-through, a design review, a talk, ...) via -SrcDir. By default the decks
    are written to a `slides/` subfolder INSIDE that source folder, so the
    rendered slides sit right next to the Markdown they came from -- intuitive,
    self-describing context (e.g. docs/walkthrough/ -> docs/walkthrough/slides/).

    Renders each numbered chapter into a self-contained HTML slide deck, plus one
    combined deck of all chapters. The source .md files are left untouched (no
    Marp front-matter committed, so they render cleanly on GitHub); this script
    injects the front-matter into temporary copies at build time.

    Requires Node.js (for `npx`). Marp CLI is fetched on first run via npx.

.PARAMETER SrcDir
    Source folder of NN-*.md chapters (default: docs/walkthrough). Relative paths
    resolve against the repo root.

.PARAMETER OutDir
    Output directory (default: <SrcDir>/slides, which is git-ignored).

.PARAMETER Footer
    Footer text stamped on every slide.

.PARAMETER Combined
    Basename of the all-chapters deck (default: walkthrough-full).

.PARAMETER Pdf
    Also export PDFs (needs a Chromium/Chrome available to Marp).

.EXAMPLE
    ./scripts/build_slides.ps1
    ./scripts/build_slides.ps1 -Pdf
    ./scripts/build_slides.ps1 -SrcDir docs/design-review -Footer 'Design Review' -Combined review-full
#>
[CmdletBinding()]
param(
    [string]$SrcDir = "docs/walkthrough",
    [string]$OutDir,
    [string]$Footer = "Semantic FAQ Chatbot - Code Walk-Through",
    [string]$Combined = "walkthrough-full",
    [switch]$Pdf
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$SrcPath  = if ([System.IO.Path]::IsPathRooted($SrcDir)) { $SrcDir } else { Join-Path $RepoRoot $SrcDir }
if (-not (Test-Path $SrcPath)) { Write-Error "Source folder not found: $SrcPath" }

# Default the output to a slides/ subfolder inside the source folder.
if (-not $OutDir) { $OutDir = Join-Path $SrcPath "slides" }
$OutPath = if ([System.IO.Path]::IsPathRooted($OutDir)) { $OutDir } else { Join-Path $RepoRoot $OutDir }

if (-not (Get-Command npx -ErrorAction SilentlyContinue)) {
    Write-Error "npx (Node.js) not found. Install Node.js from https://nodejs.org, then re-run."
}

# Run Marp CLI robustly: npm/Marp print warnings to stderr, which PowerShell would
# otherwise treat as fatal under ErrorActionPreference=Stop. We judge success by the
# process exit code instead.
function Invoke-Marp {
    param([Parameter(Mandatory)][string[]]$MarpArgs)
    $prev = $ErrorActionPreference
    $ErrorActionPreference = 'Continue'
    & npx --yes '@marp-team/marp-cli@latest' @MarpArgs 2>&1 | ForEach-Object { Write-Host $_ }
    $code = $LASTEXITCODE
    $ErrorActionPreference = $prev
    if ($code -ne 0) { throw "Marp failed (exit $code) for: $($MarpArgs -join ' ')" }
}

New-Item -ItemType Directory -Force -Path $OutPath | Out-Null

# Marp keeps relative image paths in HTML (it does not inline them), so copy the
# images next to the decks: 'assets/architecture.svg' then resolves from OutPath.
$assetsSrc = Join-Path $SrcPath "assets"
if (Test-Path (Join-Path $assetsSrc "*.svg")) {
    $assetsDst = Join-Path $OutPath "assets"
    New-Item -ItemType Directory -Force -Path $assetsDst | Out-Null
    Copy-Item (Join-Path $assetsSrc "*.svg") $assetsDst -Force -ErrorAction SilentlyContinue
}

# Keep this script ASCII-only: Windows PowerShell 5.1 reads BOM-less .ps1 files as
# ANSI, which would corrupt any non-ASCII literal here. (Chapter content keeps its
# Unicode because we read it explicitly as UTF-8 below.)
$Theme = Join-Path $SrcPath "assets/marp-theme.css"
$Config = Join-Path $RepoRoot ".marprc.yml"     # markdown options (e.g. breaks: false)
$FrontMatter = @"
---
marp: true
theme: walkthrough
paginate: true
footer: '$Footer'
---

"@

# Numbered chapters only (01-..NN-), in order. README.md / GLOSSARY.md are excluded.
$chapters = Get-ChildItem -Path $SrcPath -Filter '??-*.md' | Sort-Object Name
if (-not $chapters) { Write-Error "No chapter files (NN-*.md) found in $SrcPath" }

$tempFiles = @()
try {
    # --- one deck per chapter ---
    foreach ($ch in $chapters) {
        $tmp = Join-Path $SrcPath ("_build_" + $ch.BaseName + ".md")
        $tempFiles += $tmp
        Set-Content -Path $tmp -Value ($FrontMatter + (Get-Content $ch.FullName -Raw -Encoding UTF8)) -Encoding utf8

        $outHtml = Join-Path $OutPath ($ch.BaseName + ".html")
        Write-Host "Building $($ch.Name) -> $outHtml"
        Invoke-Marp @($tmp, "-o", $outHtml, "-c", $Config, "--no-stdin", "--allow-local-files", "--theme", $Theme)
        if ($Pdf) {
            $outPdf = Join-Path $OutPath ($ch.BaseName + ".pdf")
            Invoke-Marp @($tmp, "-o", $outPdf, "-c", $Config, "--pdf", "--no-stdin", "--allow-local-files", "--theme", $Theme)
        }
    }

    # --- one combined deck of all chapters ---
    $combinedTmp = Join-Path $SrcPath ("_build_" + $Combined + ".md")
    $tempFiles += $combinedTmp
    $parts = foreach ($ch in $chapters) { Get-Content $ch.FullName -Raw -Encoding UTF8 }
    Set-Content -Path $combinedTmp -Value ($FrontMatter + ($parts -join "`n`n---`n`n")) -Encoding utf8

    $combinedHtml = Join-Path $OutPath ($Combined + ".html")
    Write-Host "Building combined deck -> $combinedHtml"
    Invoke-Marp @($combinedTmp, "-o", $combinedHtml, "-c", $Config, "--no-stdin", "--allow-local-files", "--theme", $Theme)
    if ($Pdf) {
        Invoke-Marp @($combinedTmp, "-o", (Join-Path $OutPath ($Combined + ".pdf")), "-c", $Config, "--pdf", "--no-stdin", "--allow-local-files", "--theme", $Theme)
    }
}
finally {
    foreach ($t in $tempFiles) { if (Test-Path $t) { Remove-Item $t -Force } }
}

Write-Host ""
Write-Host "Done. Open the decks in $OutPath (e.g. $Combined.html)."
