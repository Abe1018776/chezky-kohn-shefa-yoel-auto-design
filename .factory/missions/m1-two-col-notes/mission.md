# Mission M1 — Two-column note apparatus

## Goal

Replace the current single-column note zone with the book's native two-stream
layout:

- **Right column**: `מקור השפע` — footnotes (`#fn[…]`), pours top-down, independent height.
- **Left column**: `צינור השפע` — endnotes (`#en[…]`), pours top-down, independent height.
- Rule header shows both stream titles side-by-side when endnotes present on
  the page; shows only `מקור השפע` centered when the page has footnotes but no
  endnotes (Case A in `source_uploads/pagination_study.md` §1.3).
- Columns are separated by a ~24pt gutter, RTL-ordered (right first).
- Footnote numbering continues to be bracketed Hebrew letters `[א]`, `[ב]`…,
  with the two streams maintaining **independent counters** that reset each
  time the chapter changes.

## Reference

- `source_uploads/pagination_study.md` §1.3 — the notes-block algorithm.
- `reference_scans/page_105.png` — both streams present, balanced heights (Case B).
- `reference_scans/page_109.png` — footnotes only, single centered header (Case A).
- `reference_scans/page_113.png` — same sample, different balance (Case B).

## Non-goals (deferred)

- Full-width spillover when a column overflows — that is Mission M2.
- Winged ornament glyph — that is Mission M3.

## Approach (suggested)

1. Drop the global `set footnote(numbering: …)` and keep the Hebrew bracket
   style only in our own wrappers `#fn` / `#en`.
2. Implement `#en` as a sibling of `footnote` rather than a tagged-footnote
   hack: either use Typst's `place(bottom)` directly, or emit endnotes into a
   separate state-list consumed by a `page(footer:)` function.
3. Build `note-apparatus(footnotes, endnotes)` that returns a 2-column grid:
   - If both sides have content → 2-col layout with both rule headers above.
   - If only right → 1-col with single centered rule header.
   - Each column is a flow-sized `block` that absorbs its own stream.
4. Remove the inline `set footnote.entry(separator: …)` override — the
   apparatus's rule headers replace Typst's default separator entirely.

## Acceptance

- `build/book.pdf` compiles without errors.
- Any page with both footnotes and endnotes shows two vertical columns with
  distinct headers.
- Any page with only footnotes shows a single centered header `מקור השפע`.
- Endnote numbering is independent of footnote numbering on the same page.
- Rendering time remains under 2 seconds for the full book.
- The audit script's `notes_header_found` heuristic passes on ≥ 9/10 pages.
