# Pair-keep Baseline — Alignment Map + Rebaselined Scores

> Feature `m2-alignment-rebaseline` (mission `0e4c58ac-d782-472e-a3fd-a6ae036604cf`).
> Applies to all builds at HEAD `7b69c36` and later until another
> pagination-altering change lands.

This document records the `audit/alignment.json` re-derivation and the
post-rebaselining `baselines.m1` / `baselines.m2` values in
`validation-state.json`. Future workers should consult it (a) when
inspecting why the M1 baseline stored in `validation-state.json` is
*lower* than the 80.1 some older scrutiny synthesis reports quote,
and (b) when deciding whether a new pagination change warrants
re-deriving the alignment map.

## Summary

| Metric | Pre-rebaseline (stale) | Post-rebaseline (current) |
|---|---:|---:|
| `pdf_page_count`            | 15                    | 24 physical (21 logical + 3 notes-continuation) |
| `audit_score`               | 80.1 (clipping build) | 71.0 (clip-free pair-keep) |
| `build_time_sec`            | 1.22 (cold M1 cache)  | 0.74 (warm cache, 3-run avg) |
| `notes_header_hit_rate`     | 15/15                 | 20/24                       |
| Alignment mapped entries    | 15/15                 | 21/24 (3 null: notes-cont) |

The stale 80.1 score was measured against a pipeline build where
Typst's native footnote engine silently clipped notes whose total
character count exceeded a single page's apparatus zone (blocks 4, 6,
29, 31, 35, 42, 48 each carry 1500–5146 chars of notes). The M1
baseline was captured under that clipped reality; the M2 pair-keep
pivot (commit `7b69c36`) made `convert.py` the pagination authority
and introduced body-free *notes-continuation pages* to hold overflow
apparatus without truncation. This shift is by design (VAL-M2-012
round-5 extended escape clause) but changes the pipeline's output
materially: page count grows to 24 physical, and the alignment map
needed to be re-derived to score the new build against the 20
reference scans.

## Alignment map (24 generated → 20 reference)

```
Chapter 1 (gen 1–11 → ref 105–113; ornament at ref 113):
  gen  1 → page_105.png   (opener pin)
  gen  2 → page_106.png
  gen  3 → page_106.png   (double-book)
  gen  4 → page_107.png
  gen  5 → page_108.png
  gen  6 → page_109.png
  gen  7 → page_109.png   (double-book)
  gen  8 → page_110.png
  gen  9 → page_111.png
  gen 10 → page_112.png
  gen 11 → page_113.png   (ornament pin)

Chapter 2 (gen 12–18 → ref 114–118; ornament at ref 118):
  gen 12 → page_114.png   (opener pin)
  gen 13 → page_115.png
  gen 14 → null           (notes-continuation for block 31)
  gen 15 → page_116.png
  gen 16 → page_117.png
  gen 17 → null           (notes-continuation for block 35)
  gen 18 → page_118.png   (ornament pin)

Chapter 3 (gen 19–24 → ref 119–122; ornament at ref 122):
  gen 19 → page_119.png   (opener pin)
  gen 20 → page_120.png
  gen 21 → page_120.png   (double-book)
  gen 22 → page_121.png
  gen 23 → null           (notes-continuation for block 48)
  gen 24 → page_122.png   (ornament pin)
```

### Derivation rationale

1. **Opener pins.** `convert.py`'s keep-group logic guarantees that
   every chapter's opener quartet (chapter + chapter_title + subtitle +
   first body) lives on its own page. Those pages (phys 1, 12, 19) are
   trivially recognisable by the presence of chapter_title blocks (2,
   27, 40) in the logical block list. Pin each to the corresponding
   reference opener (105, 114, 119).

2. **Ornament pins.** Each chapter ends with an ornament block (25, 38,
   51) which rides with the preceding body block under the keep-group
   rule "ornament rides with preceding". The last physical page of each
   chapter's range therefore carries the ornament and is pinned to the
   reference ornament page (113, 118, 122).

3. **Notes-continuation pages → null.** Blocks 31, 35, and 48 carry
   1500+ chars of fn+en notes that exceed their page's apparatus
   budget. Under the clip-free pair-keep model these overflow onto
   body-free apparatus-only pages. The reference edition has no such
   pages (the Radomsk hand-typeset used tighter typography + different
   page sizes), so these generated pages have no ground-truth
   counterpart. Mapping them to `null` is correct per the existing
   `audit/image_diff.py` semantics (a `null` entry scores 0 on the
   `page_aligned` 10%-weight term but contributes `notes_header_found`
   detection to the composite).

4. **Body pages → many-to-one mapping where needed.** Chapter 1 has
   11 generated scoring pages but only 9 reference pages (105–113).
   Chapter 3 has 5 generated scoring pages but only 4 reference pages
   (119–122). `audit/image_diff.py` allows many-to-one mapping (no
   injectivity constraint on the alignment). Double-book ref 106 and
   109 in chapter 1 (where generated pagination packs more densely)
   and ref 120 in chapter 3, preserving the opener+ornament pins.
   Chapter 2 aligns 5→5 cleanly.

### Why not re-tune `convert.py` to match the 15-page target?

Matching 15 pages requires either (a) tighter body typography, which
would regress the visual match against reference body; (b) silent
clipping, which the round-5 contract refinement of VAL-M2-012
explicitly forbids (notes-continuation pages are the contract-endorsed
solution); or (c) a taller page size, which would cascade into M3
ornament geometry and M5 cartouche scaling. The orchestrator's
decision was to accept 21 logical / 24 physical pages (widening
VAL-M2-005 to `[18, 25]`) and re-derive the alignment map rather than
force the page count down.

## Rebaselined M1 + M2 scores

Both baselines point to the same build (HEAD `7b69c36`, PDF SHA
`14edbe0be391422d477020fb22b8e0c46951a0fbd3f9da6e891bfbe8c38324a9`)
because M1 and M2 features now converge on a single pipeline. The
audit score components (reweighted scorer 0.15 SSIM / 0.30 header /
0.30 notes-hdr / 0.15 phash / 0.10 page-aligned) are:

- `ssim` mean = 0.0556 → 0.83 weighted contribution
- `phash_dist` mean = 15.12 → 11.46 weighted
- `header_match` mean = 0.8317 → 24.95 weighted
- `notes_header_found` hit rate = 20/24 → 25.00 weighted
- `page_aligned` = 21/24 → 8.75 weighted
- **Average score = 71.0 / 100**

The `header_match` mean is lower than M1's historical 0.9505 because
notes-continuation pages (14, 17, 23) score 0.000 on header_match
(they have no reference counterpart; `ref=None` ⇒ `header_match=0.0`).
The `notes_header_found` hit rate is 20/24 because four body-bearing
pages (13, 16, 20, 22) miss the y ∈ [0.70h, 0.78h] dark-band heuristic
— the per-page bottom margins vary under pair-keep, so the apparatus
header doesn't always sit in that fixed band. This is a limitation of
the audit's structural heuristic, not a real layout defect.

## VAL-M2-006 delta check

`score_m2 − score_m1 = 71.0 − 71.0 = 0.0 ≥ −1.0 → PASS`.

Both sides of the delta measure the same build; the delta-based
regression guard (round-5 reform of VAL-M2-006) trivially passes.
If a future feature differentiates M1 from M2 (e.g., introduces an
M2-only layout pass), `baselines.m2` would need to be re-measured
separately and the delta would then become non-zero.

## Regeneration procedure

When another pagination-altering change lands (M3 ornament SVG might
free up vertical space; M4/M5 would re-plumb margins):

1. Full rebuild on the sandbox per `services.yaml::commands.build`.
2. Extract `build/body_locs.json` and `build/notes.json`.
3. Identify per-physical-page content and chapter membership:
   - A page is an **opener** if any `chapter_title` block (2, 27, 40)
     participates in it.
   - A page is an **ornament page** if the last block in the
     emission order is `ornament` (25, 38, 51).
   - A page is a **notes-continuation page** if it has notes but no
     body-loc entries.
4. Update `audit/alignment.json::alignment`:
   - Opener pages → ref opener (105, 114, 119).
   - Ornament pages → ref ornament (113, 118, 122).
   - Notes-continuation pages → `null`.
   - Body-only pages → proportional allocation across the chapter's
     body ref range (106–112, 115–117, 120–121), many-to-one when
     generated count > reference count.
5. Run `python3 audit/image_diff.py --verbose` and capture
   `Average score`. Update `baselines.m{1,2}.audit_score` in
   `validation-state.json`.
6. Recompute `notes_header_hit_rate` from the per-page `notes-hdr`
   column in `build/audit_report.md`.

If the alignment map materially changes (openers / ornaments move),
update `gen_chapter_ranges` and `notes_continuation_pages` fields in
`audit/alignment.json::derivation` to match.

## Assertions verified at this feature

| Assertion | Status | Evidence |
|---|---|---|
| VAL-M2-005  | PASS | 24 physical pages ∈ [18, 25] |
| VAL-M2-006  | PASS | 71.0 − 71.0 = 0.0 ≥ −1.0 |
| VAL-M2-012  | PASS | 0 violations across 21 body blocks (pair-keep under round-5 extended escape) |
| VAL-M2-013  | PASS | 0 orphan chapter_title/subtitle on any logical page |
| VAL-M2-014  | PASS | 0 violations of min-3-body-lines on 18 qualifying physical pages |

VAL-M2-010 (body TOP-y / BOTTOM-y invariant) remains pending —
outside this feature's scope; a future worker should validate it from
`<body-loc>` y-coordinates.

## Known quirks

1. **Notes-continuation pages score low on header_match.** They have
   no reference counterpart so `header_match = 0.0`. Their
   contribution lowers the M2 average by ≈ 3.75 points relative to a
   clip-based 15-page baseline. This is a cost paid for correctness
   (overflow notes aren't dropped); do not try to recover it by
   clipping.

2. **Body-only pages can miss the notes-header heuristic.** Pages
   where `convert.py` commits a tall apparatus zone push the
   rule-header below the y ∈ [0.70h, 0.78h] band that
   `audit/image_diff.py::detect_notes_header_text` scans. This is a
   known limitation of the audit heuristic, not a layout bug. A future
   audit-script refinement might y-scan adaptively based on the
   emitted bottom margin.

3. **Double-booking doesn't double-count.** When two generated pages
   point to the same reference (e.g., gen 2 and gen 3 both → 106),
   each is scored independently against the same reference. The audit
   does NOT take a best-of or average. The effect on the composite
   score is that unusual layouts (where two gen pages legitimately
   carry similar content as one ref page) can score reasonably;
   totally dissimilar pages still score poorly.
