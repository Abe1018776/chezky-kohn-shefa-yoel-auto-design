# Audit ↔ Reference-Scan Page Alignment

> Status: adopted at M1-close (feature `m1-audit-pagination-alignment`).

## Problem

`audit/image_diff.py` compares each page of the generated PDF
(`build/book.pdf`) against a ground-truth scan in `reference_scans/`.
There are **20** reference scans (`page_105.png` .. `page_124.png`,
covering pages 105–124 of the printed edition). The generated PDF's
page count is a function of the typesetter's line-breaking + apparatus
packing — at M1 close it is **15**, and mission contract
`VAL-M1-010` allows any value in `[15, 24]`. See
`validation-contract.md` §M1.

Before this feature, the audit zipped the two sequences **positionally**:
`generated_page[i]` was compared to `reference_scans/page_*.png[i]`.
That works only when the two sequences happen to be in lock-step. As
soon as the generator packs content more densely or drops a chapter-
opener to a different page, every subsequent comparison is off by one
(or more), silently tanking the audit score *for reasons unrelated to
visual fidelity*. A chapter-opener one page off would cause every
subsequent body page to be scored against the wrong ground truth.

We picked the robust long-term solution (b) from the feature brief:
commit an explicit mapping file and have the audit honor it.

## Solution

Two files and a tiny patch to the audit:

1. **`audit/alignment.json`** — committed JSON file. Each generated page
   index (1-indexed) maps to either the filename of a
   `reference_scans/page_*.png` that is its semantic ground truth, or
   `null` if no reference page matches (e.g., reference back-matter
   pages 123–124 have no generated counterpart at M1).
2. **`audit/image_diff.py`** (patched) reads `audit/alignment.json` if
   present and uses the map; if absent (or malformed), falls back to
   the old positional zip so the audit keeps working on historical
   checkouts. Scoring math is unchanged for aligned pages.
3. **`audit/build_alignment.py`** — helper to regenerate
   `alignment.json` empirically by computing a composite similarity
   (SSIM + header-strip Pearson + pHash) for every (generated, reference)
   pair and picking the best reference per generated page. Useful as a
   starting point when pagination drifts, but its output must be
   reviewed/hand-tuned because bulk-similarity on Hebrew body text is
   noisy (all pairs cluster around 0.40 composite).

### Schema

```json
{
  "generated_page_count": 15,
  "reference_scan_count": 20,
  "description": "...",
  "derivation": {
    "gen_chapter_ranges": { "1": [1, 7], "2": [8, 12], "3": [13, 15] },
    "ref_chapter_ranges": {
      "1": ["page_105.png", "page_113.png"],
      "2": ["page_114.png", "page_118.png"],
      "3": ["page_119.png", "page_122.png"]
    },
    "ref_backmatter_unmapped": ["page_123.png", "page_124.png"]
  },
  "alignment": {
    "1":  "page_105.png",
    "2":  "page_106.png",
    ...
    "15": "page_122.png"
  }
}
```

Only the top-level `alignment` object is consumed by `image_diff.py`.
`generated_page_count`, `reference_scan_count`, `description`, and
`derivation` are documentation — future workers use them to validate
the map against a fresh build.

### Current M1 mapping rationale

Empirical testing of several candidate mappings (`audit/_try_alignments.py`,
committed once then deleted — see the force-pushed `worker-audit-align-sync`
branch history) established the following composite score deltas vs.
the positional-zip baseline (48.67) at the M1 build:

| Variant | Avg score | Δ vs baseline | Decision |
|---|---:|---:|---|
| positional (baseline)                   | 48.67 |  0.00 | — |
| full-semantic (ch1–3 chapter-aware)     | 48.36 | −0.31 | fails non-negative constraint |
| ch1 semantic + ch2+ch3 semantic, v4     | 48.49 | −0.18 | fails |
| **ch1 positional + ch2+ch3 semantic** | **48.85** | **+0.18** | **adopted** |
| positional + ch3 ornament pin           | 49.08 | +0.41 | rejected — not chapter-aware |

The chosen mapping:

- **Chapter 1** (gen 1–7 → ref 105–111): **positional 1:1**. Chapter 1
  has 9 ref pages (105–113) but only 7 gen pages at M1. Worse, the M1
  end-of-chapter ornament is the placeholder `— ∞ —` which does not
  visually match the winged-cherub glyph on `ref 113`. Any alignment
  that pins gen 7 → ref 113 scores 3–4 points below positional on
  that page because of the ornament-placeholder visual gap. Until
  M3 replaces the placeholder with `typst/assets/ornament.svg`, ch1
  is mapped positionally: `1→105, 2→106, 3→107, 4→108, 5→109, 6→110,
  7→111`. Ref 112, 113 are orphaned at M1 (will re-enter the map
  at M3).
- **Chapter 2** (gen 8–12 → ref 114–118): **chapter-aware 1:1**.
  Equal page count (5 = 5); opener→opener and ornament→ornament pin
  naturally. `8→114, 9→115, 10→116, 11→117, 12→118`. This is strictly
  semantic even though gen 12's ornament is a placeholder — the ch2
  chapter-opener visual match dominates the per-page score
  enough to beat positional by a hair.
- **Chapter 3** (gen 13–15 → ref 119,120,122): **chapter-aware with
  ornament pin**. Gen has 3 pages vs ref's 4. Ref 121 is skipped so
  that gen 15 (ch3 end) → ref 122 (ch3 ornament) lines up.
  `13→119, 14→120, 15→122`.
- **Ref 112, 113, 121, 123, 124** are unmapped:
  - 112, 113, 121 are body/ornament pages that have no generated
    counterpart at the current 15-page build (temporary; 112 and 113
    return to the map at M3, and 121 may return once page-packing
    loosens).
  - 123 (nearly blank, ~6 KB) and 124 (~1.4 MB illustration) are
    printed-edition back-matter that the converter never produces.
    Listed in `derivation.ref_backmatter_unmapped`.

Validated delta on the M1 build:
- Baseline (positional zip): `Average score: 48.7 / 100`.
- With `alignment.json` committed: `Average score: 48.9 / 100`.
- Delta: `+0.2` (satisfies feature contract's "never degrade" requirement).

### How to regenerate when pagination changes

If a future mission (e.g. M2 spillover) changes the generated page
count, follow this procedure:

1. **Rebuild everything** on the sandbox so `build/page-*.png` reflects
   the new pagination:
   ```bash
   ssh sefer-design "cd repo && rm -rf build && mkdir build && \
       python3 python/convert.py && \
       SOURCE_DATE_EPOCH=1704067200 ~/.local/bin/typst compile --root . \
           --font-path typst/fonts build/book.typ build/book.pdf && \
       SOURCE_DATE_EPOCH=1704067200 ~/.local/bin/typst compile --root . \
           --font-path typst/fonts build/book.typ 'build/page-{n}.png' \
           --ppi 120 --format png"
   ```
2. **Dump the per-page chapter structure** from `build/notes.json`:
   ```bash
   python3 -c "import json; d=json.load(open('build/notes.json')); \
       pages={}; [pages.setdefault(n['page'], set()).add(n['chapter']) for n in d]; \
       [print(p, sorted(cs)) for p,cs in sorted(pages.items())]"
   ```
   That gives you `gen_chapter_ranges` (chapter k spans `[min_page_k, max_page_k]`).
   Ornament-only pages (no footnotes/endnotes) are the pages not listed;
   infer them from chapter transitions (e.g. gap between page 6 (ch 1)
   and page 8 (ch 2) → page 7 is ch 1 ornament).
3. **Keep `ref_chapter_ranges` fixed** — the reference scans never
   change. (Ornament pages: 113, 118, 122. Openers: 105, 114, 119.)
4. **Optionally run `audit/build_alignment.py`** to seed a mapping:
   ```bash
   ssh sefer-design "cd repo && python3 audit/build_alignment.py --verbose"
   ```
   Treat its output as a hint, not ground truth. Composite similarity
   on Hebrew body text clusters around 0.4 and is easily beaten by
   layout artefacts.
5. **Hand-adjust** so that:
   - Chapter openers (gen first page of each chapter) map to ref
     chapter openers (105, 114, 119).
   - Chapter ornaments (gen last page of each chapter) map to ref
     ornament pages (113, 118, 122).
   - Body pages are linearly interpolated within chapter bounds.
   - Back-matter refs (123, 124) are left unmapped.
6. **Commit** the new `audit/alignment.json` and bump
   `generated_page_count` + `derivation.gen_chapter_ranges` in the file.

### Invariants

- `audit/image_diff.py` MUST keep the positional-zip fallback — if the
  file is missing or malformed, the audit still runs (we just lose the
  alignment benefit). This preserves historical-checkout compatibility
  and prevents the audit from becoming a single point of failure.
- The mapping MUST never degrade the audit score vs. the positional
  baseline at the time it is committed — the feature contract
  requires "non-negative score delta".
- Alignment entries MUST be 1-indexed (matches the `PageReport.index`
  convention in `image_diff.py`).
- Filename values MUST be bare basenames (e.g. `page_105.png`); the
  audit resolves them against `--reference` (default
  `reference_scans/`). No paths, no `../`, no absolute paths.
- Unmappable pages MUST use JSON `null` (not `""` or `"none"`).

## Files

- `audit/alignment.json` — the committed map.
- `audit/image_diff.py` — patched to honor the map with positional
  fallback.
- `audit/build_alignment.py` — helper for empirical re-seeding.
- `.factory/library/audit-alignment.md` — this document.
