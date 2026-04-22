# Validation Contract — M3 Winged ornament

## A1 — Build is clean

- **Surface**: shell
- **Pass**: converter + compile exit 0.

## A2 — Ornament appears on exactly the end-of-chapter pages

- **Surface**: rendered PNGs, JSON source
- **Pass**: The set of pages that contain a non-text graphic glyph in the
  lower third (excluding the notes zone) is exactly the set of JSON-derived
  "end-of-chapter" positions (blocks 27, 40, 51 — immediately before `פרק ב`,
  `פרק ג`, end-of-book).
- **Evidence**: for each such page, a cropped region screenshot showing the
  ornament, plus a list confirming no other page has an ornament.

## A3 — Ornament renders visually correct

- **Surface**: the cropped ornament image
- **Pass**: The ornament is either:
    - the SVG asset from `typst/assets/ornament.svg` (preferred), rendered
      at 10–16mm wide, horizontally centered, or
    - a Unicode / font-glyph selected for shape fidelity to the reference.
- **Evidence**: side-by-side crop of our ornament and the corresponding
  reference scan's ornament.

## A4 — Ornament is horizontally centered

- **Surface**: cropped ornament region
- **Pass**: Centroid of the ornament is within 2mm of the page's horizontal
  midline.

## A5 — No regression

- **Surface**: `build/audit_report.md`
- **Pass**: Audit average score does not decrease from the previous mission's
  baseline.
