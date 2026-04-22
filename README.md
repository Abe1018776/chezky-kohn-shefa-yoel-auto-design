# Shefa Shlomo — Automated Sefer Layout

An end-to-end pipeline that takes the structured JSON extraction of a Hebrew
sefer (religious book) and produces a typeset PDF that matches the 8-zone
page layout of the published edition:

1. Running header (folio letter in gematria, `שפע`, `שלמה`, shaar/chapter label)
2. Chapter cartouche (`פרק א`, `פרק ב`, …)
3. Vowelised chapter title
4. Section subtitle (grey, letter-spaced)
5. Main body (justified, RTL, `א. / ב. / ג.` markers, inline call-outs `[א]`)
6. Two-column note apparatus — מקור השפע (right) + צינור השפע (left)
7. Spillover zone (full-width continuation of column overflow)
8. End-of-chapter ornament

## Pipeline

```
source_uploads/docx_content_with_notes.json
         │
         ▼
python/convert.py                     ← classify blocks per pagination_study.md
         │                              inline [א] → #fn[…]   or   #en[…]
         ▼
build/book.typ  ──┐
typst/template.typ│    typst compile --root . --font-path typst/fonts
typst/fonts/ ─────┤
                  ▼
build/book.pdf
```

## Quickstart

```bash
# Convert JSON → Typst source
python3 python/convert.py

# Compile Typst → PDF
~/.local/bin/typst compile --root . --font-path typst/fonts \
    build/book.typ build/book.pdf

# Render per-page previews (PNG)
~/.local/bin/typst compile --root . --font-path typst/fonts \
    build/book.typ build/page-{n}.png --ppi 120 --format png

# Run the audit against the reference scans
python3 audit/image_diff.py
```

## Parallel tracks

- **Track A — Typst (fidelity):** `typst/template.typ` + `python/convert.py`.
  Produces `build/book.pdf` in one sub-second compile. Handles RTL, Hebrew
  gematria folio numbering, chapter cartouche, subtitle styling, pinned
  footnotes with Hebrew bracket call-outs, and `מקור השפע` rule-header.
- **Track B — Paged.js audit:** `audit/paged/` scaffolds an HTML+CSS rendering
  using the GCPM spec; `audit/image_diff.py` compares rendered pages pixel-wise
  against the 20 reference scans and produces a markdown report
  (`build/audit_report.md`).

## Current status (phase 1)

- [x] JSON classification (chapter / chapter_title / subtitle / body / ornament)
- [x] Positional call-out pairing with `footnotes[]` / `endnotes[]`
- [x] 170×240mm RTL Hebrew page, Noto Serif Hebrew
- [x] Gematria folio counter (starts at 77 → `עז`)
- [x] Running header with per-page shaar/chapter rotation
- [x] Cartouche + vowelised chapter title
- [x] Pinned footnote apparatus with Hebrew `[א]` brackets
- [x] `─── מקור השפע ───` rule header above notes
- [x] End-of-chapter ornament (`— ∞ —` placeholder)
- [x] Build: 11 pages, 118KB, sub-second compile
- [x] Audit harness (header-strip diff 94.8%, notes-header detected 10/11)

## Phase 2 gaps

- [ ] True two-column note zone split (מקור right / צינור left, independent heights)
- [ ] Full-width spillover below the 2-col block (for long endnotes like the
      Rebbe-of-Radomsk story on reference page 117)
- [ ] Winged-cherub ornament (currently `— ∞ —`)
- [ ] Oval cartouche curve (currently rounded rectangle)
- [ ] Tight byte-level reproduction: current audit score 50/100; target 80+
