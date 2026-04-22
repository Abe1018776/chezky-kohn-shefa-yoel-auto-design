# Validation Contract — M1 Two-column notes

Each assertion has an ID, a testable surface (build output / PDF rendering /
audit report), the pass criterion, and the required evidence.

---

## A1 — Build is clean

- **Surface**: shell
- **Pass**: `python3 python/convert.py && typst compile --root . --font-path typst/fonts build/book.typ build/book.pdf` exits 0 with no compile errors.
- **Evidence**: stdout of both commands.

## A2 — Any page with endnotes has two visible columns

- **Surface**: rendered PNGs `build/page-*.png`
- **Pass**: For the pages known to carry endnotes (per JSON: blocks with
  non-empty `endnotes`, currently blocks 4, 6, 16, 18, 31, 35, 37, 48, 50),
  the rendered page has two visually distinct column blocks in the lower
  third, separated by a gutter of at least 6mm.
- **Evidence**: annotated screenshot with both column bounding boxes drawn.

## A3 — Pages with footnotes only show a single centered rule header

- **Surface**: rendered PNGs
- **Pass**: On pages whose visible blocks carry footnotes but no endnotes,
  exactly one `─── מקור השפע ───` header is centered above the notes zone.
- **Evidence**: cropped strip from the notes area on one such page.

## A4 — Independent Hebrew numbering streams

- **Surface**: rendered PNGs
- **Pass**: On any page carrying both streams, both the right-column first
  note and the left-column first note are numbered `[א]` (the two streams
  do not share a counter).
- **Evidence**: cropped strip from both columns showing the markers.

## A5 — Full book still fits in ≤ 12 pages

- **Surface**: `build/book.pdf`
- **Pass**: PDF page count is between 9 and 12 (reference is 17 active
  content pages; current single-column output is 10).
- **Evidence**: output of `pdfinfo` or a Python `PyPDF` page count.

## A6 — Audit score does not regress

- **Surface**: `build/audit_report.md`
- **Pass**: Running `python3 audit/image_diff.py` yields an average score
  ≥ 48.0 (current baseline).
- **Evidence**: tail of the audit report.
