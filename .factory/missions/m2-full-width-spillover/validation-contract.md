# Validation Contract — M2 Full-width spillover

## A1 — Build is clean

- **Surface**: shell
- **Pass**: converter + compile exit 0 without errors.

## A2 — Spillover zone exists under the columns

- **Surface**: `build/page-*.png`
- **Pass**: At least one page contains a full-width paragraph block that
  starts beneath both note columns, spanning from the right margin to the
  left margin, in the commentary type size (PFT_Vilna 9pt).
- **Evidence**: cropped bottom-third of the page.

## A3 — Spillover preserves stream order

- **Surface**: `build/book.pdf`
- **Pass**: On a page where the right column overflows into spillover, the
  first paragraph of the spillover is the continuation of the right column's
  last footnote. On a page where only the left (endnote) column overflows,
  the spillover begins with the endnote continuation.
- **Evidence**: text extraction via `pdftotext` (or PyPDF) showing the
  right-column last note's final sentence is directly followed by the
  spillover text.

## A4 — The Rebbe-of-Radomsk endnote lands correctly

- **Surface**: `build/page-*.png` corresponding to JSON block 16 (endnote 3
  begins "יש לציין מה שהביא רבינו (תפארת שלמה פרשת שופטים)…" ).
- **Pass**: That endnote visibly occupies the left column and bleeds into
  the spillover zone at the bottom of the same page.
- **Evidence**: full-page screenshot with column/spillover regions annotated.

## A5 — Page count does not increase

- **Surface**: PDF page count
- **Pass**: Page count is equal to or fewer than the M1 output page count.

## A6 — Audit score improves

- **Surface**: `build/audit_report.md`
- **Pass**: Average score ≥ 55.0.
