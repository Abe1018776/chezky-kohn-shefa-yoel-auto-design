# Mission M2 — Full-width spillover zone

## Prerequisite

Mission M1 (two-column notes) must be merged first; the spillover zone is
the third row of the apparatus `grid` created in M1.

## Goal

When either column of the note apparatus cannot contain its full text within
the reserved ~40% of page height, push the remainder into a single
**full-page-width** paragraph zone below both columns, preserving stream
order (footnotes continue first, then endnotes), at the same smaller
commentary type size.

This is the "column-then-spill" pattern seen in `reference_scans/page_105.png`
and — most dramatically — `reference_scans/page_117.png` (the 1,700-character
Rebbe-of-Radomsk endnote).

## Algorithm (from `pagination_study.md` §1.3)

```
1. Lay out body for page → remember y-offset where it ended.
2. Under the body, reserve a strip down to 85% of page height.
   Divide into two columns separated by a gutter (~24pt).
3. Pour all footnotes into the right column top-down until full OR exhausted.
4. Pour all endnotes into the left column top-down until full OR exhausted.
5. Any footnote/endnote text that did not fit spills into a single
   full-width paragraph zone below both columns, preserving order
   (footnotes first, then endnotes), same smaller type size.
```

## Approach (suggested)

Typst does not ship with a primitive for "measure my content against a fixed
height then flow the remainder elsewhere." Two viable paths:

### Path A — Pre-partition in Python

Extend `python/convert.py` to:
1. Estimate column capacity in characters (e.g. ~900 chars per column at
   `_note-col-height: 85mm`, PFT_Vilna 9pt).
2. Split each stream into `fits_in_column[]` + `spills_to_full_width[]`.
3. Emit two separate Typst calls per page: `#fn-col[...]`, `#en-col[...]`,
   `#spillover[...]`.
4. Template renders whichever blocks are non-empty.

### Path B — Native Typst measure + place

Use Typst's `measure()` + `layout()` to compute the rendered height of each
column's content, compare to `_note-col-height`, and emit the overflow into
a `place(bottom)` full-width block.

Path A is simpler; Path B keeps the JSON "pure" and the logic in the template.
Pick Path A first, graduate to B later.

## Acceptance

- Pages 1, 4, 7 (equivalents of 105, 108, 111 in the reference) show a
  full-width paragraph continuing the right column, underneath both columns.
- Page containing the Rebbe-of-Radomsk endnote (block 16 / endnote 3) shows
  that endnote occupying the left column + all of the spillover.
- Total page count does not grow: spillover absorbs overflow rather than
  creating new pages.
- The audit score rises to ≥ 55.0 (from M1 baseline).
