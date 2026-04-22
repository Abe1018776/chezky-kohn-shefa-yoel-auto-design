# AGENTS.md — Mission M2

## Prerequisite
M1 must be complete (`validation-state.json` for M1 all green).

## Build

Same as M1 (see `.factory/missions/m1-two-col-notes/AGENTS.md`).

Additional dependency: you will likely want `pdftotext` for A3. Install:
```bash
# Try: apt-get install poppler-utils  (not available — no sudo)
# Fallback: pure-Python via pypdf
python3 -m pip install --user --break-system-packages pypdf
```

## Testing & Validation Guidance

- For A2 / A4, inspect `build/page-*.png` visually and sanity-check the
  layout geometry.
- For A3, run `pdftotext build/book.pdf - | head -200` (or a PyPDF text
  extraction) and verify the column→spillover ordering by reading the text
  stream.
- For A5, `~/.local/bin/typst compile` prints the page count; or use
  `python3 -c "import pypdf; print(len(pypdf.PdfReader('build/book.pdf').pages))"`.
- For A6, `python3 audit/image_diff.py` then `grep '^**Average' build/audit_report.md`.

## Known source-data landmarks

- JSON block **16** has endnote id "3" which begins with "יש לציין מה שהביא
  רבינו (תפארת שלמה פרשת שופטים)…" — this is the longest single endnote in
  the corpus (1,700+ chars) and must demonstrate the spillover.
- JSON block **4** has endnote id "1" — the "רבינו היה ידוע כיודע נגן..." story,
  also long (~2,500 chars); must also spill.
