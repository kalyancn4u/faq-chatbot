<#
.SYNOPSIS
    Build the code walk-through chapters into HTML slide decks with Marp.

.DESCRIPTION
    Renders each numbered chapter in docs/walkthrough/ into a self-contained HTML
    slide deck, plus one combined deck of all chapters. The source .md files are
    left untouched (no Marp front-matter committed, so they render cleanly on
    GitHub); this script injects the front-matter into temporary copies at build
    time.

    Requires Node.js (for `npx`). Marp CLI is fetched on first run via npx.

.PARAMETER OutDir
    Output directory (default: build/slides, which is git-ignored).

.PARAMETER Pdf
    Also export PDFs (needs a Chromium/Chrome available to Marp).

.EXAMPLE
    ./scripts/build_slides.ps1
    ./scripts/build_slides.ps1 -Pdf
#>
[CmdletBinding()]
param(
    [string]$OutDir = "build/slides",
    [switch]$Pdf
)

$ErrorActionPreference = "Stop"

$RepoRoot = Split-Path $PSScriptRoot -Parent
$WalkDir  = Join-Path $RepoRoot "docs/walkthrough"
$OutPath  = if ([System.IO.Path]::IsPathRooted($OutDir)) { $OutDir } else { Join-Path $RepoRoot $OutDir }

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
$assetsDst = Join-Path $OutPath "assets"
New-Item -ItemType Directory -Force -Path $assetsDst | Out-Null
Copy-Item (Join-Path $WalkDir "assets/*.svg") $assetsDst -Force -ErrorAction SilentlyContinue

# Keep this script ASCII-only: Windows PowerShell 5.1 reads BOM-less .ps1 files as
# ANSI, which would corrupt any non-ASCII literal here. (Chapter content keeps its
# Unicode because we read it explicitly as UTF-8 below.)
$Theme = Join-Path $WalkDir "assets/marp-theme.css"
$FrontMatter = @"
---
marp: true
theme: walkthrough
paginate: true
footer: 'Semantic FAQ Chatbot - Code Walk-Through'
---

"@

# Numbered chapters only (01-..10-), in order. README.md / GLOSSARY.md are excluded.
$chapters = Get-ChildItem -Path $WalkDir -Filter '??-*.md' | Sort-Object Name
if (-not $chapters) { Write-Error "No chapter files found in $WalkDir" }

$tempFiles = @()
try {
    # --- one deck per chapter ---
    foreach ($ch in $chapters) {
        $tmp = Join-Path $WalkDir ("_build_" + $ch.BaseName + ".md")
        $tempFiles += $tmp
        Set-Content -Path $tmp -Value ($FrontMatter + (Get-Content $ch.FullName -Raw -Encoding UTF8)) -Encoding utf8

        $outHtml = Join-Path $OutPath ($ch.BaseName + ".html")
        Write-Host "Building $($ch.Name) -> $outHtml"
        Invoke-Marp @($tmp, "-o", $outHtml, "--allow-local-files", "--theme", $Theme)
        if ($Pdf) {
            $outPdf = Join-Path $OutPath ($ch.BaseName + ".pdf")
            Invoke-Marp @($tmp, "-o", $outPdf, "--pdf", "--allow-local-files", "--theme", $Theme)
        }
    }

    # --- one combined deck of all chapters ---
    $combinedTmp = Join-Path $WalkDir "_build_walkthrough-full.md"
    $tempFiles += $combinedTmp
    $parts = foreach ($ch in $chapters) { Get-Content $ch.FullName -Raw -Encoding UTF8 }
    Set-Content -Path $combinedTmp -Value ($FrontMatter + ($parts -join "`n`n---`n`n")) -Encoding utf8

    $combinedHtml = Join-Path $OutPath "walkthrough-full.html"
    Write-Host "Building combined deck -> $combinedHtml"
    Invoke-Marp @($combinedTmp, "-o", $combinedHtml, "--allow-local-files", "--theme", $Theme)
    if ($Pdf) {
        Invoke-Marp @($combinedTmp, "-o", (Join-Path $OutPath "walkthrough-full.pdf"), "--pdf", "--allow-local-files", "--theme", $Theme)
    }
}
finally {
    foreach ($t in $tempFiles) { if (Test-Path $t) { Remove-Item $t -Force } }
}

Write-Host ""
Write-Host "Done. Open the decks in $OutPath (e.g. walkthrough-full.html)."
