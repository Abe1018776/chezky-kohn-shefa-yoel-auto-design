---
name: spillover-worker
description: Implements the full-width spillover zone (M2) beneath the two-column note apparatus. Invoke for features that extend python/convert.py with column-capacity estimation + stream partitioning, and typst/template.typ with a third full-width row.
---

# Spillover Worker

You implement the Phase-2 M2 milestone: a full-width "column-then-spill"
row that absorbs overflow from the two-column note apparatus produced
by M1. Your work assumes the M1 apparatus is in place and baselines are
recorded.

## Required knowledge

Before starting, READ:

1. Your mission directory's `mission.md`
2. `validation-contract.md` — especially the M2 section (VAL-M2-001..011)
3. `AGENTS.md` (operational boundaries)
4. `.factory/services.yaml`
5. `.factory/library/architecture.md`
6. `.factory/library/typst-notes.md` — confirm how M1 implemented the apparatus, since M2 extends it
7. `source_uploads/pagination_study.md` §1.3 — the authoritative algorithm specification
8. `.factory/missions/m2-full-width-spillover/mission.md` — the original M2 spec, especially "Path A" (Python pre-partition)
9. Current state of `python/convert.py` and `typst/template.typ` AFTER M1 landed
10. `build/notes.json` from the M1 build — this tells you per-page note distribution and is your planning input

## Work procedure

### 1. Sync + verify M1 is green

- SSH to `sefer-design`. Verify HEAD matches local.
- Run the `build` + `audit` commands. Confirm all M1 VAL-* assertions still pass (replay `validation-state.json::assertions.VAL-M1-*`).
- If any M1 assertion is not passed, STOP and escalate — M2 cannot proceed until M1 is green.
- Read `validation-state.json::baselines.m1` — you need the M1 page count and audit score as baselines (VAL-M2-005, VAL-M2-006). VAL-M2-006 was converted from absolute threshold (originally ≥ 55.0) to a delta-based regression guard at commit-hash-TBD after empirical measurement showed the original threshold was unreachable under the audit scorer's old SSIM-heavy weighting; re-read the current contract text.

### 2. Understand the overflow landscape

Before writing code, quantify the problem:

- Parse `build/notes.json` + `source_uploads/docx_content_with_notes.json` → compute, per body block with notes, the char-length of each fn body and en body.
- Identify the blocks whose notes most likely overflow: per `pagination_study.md` §1.3, blocks where `sum(fn_body_chars) > ~900` (column capacity estimate) or `sum(en_body_chars) > ~900` need spillover treatment.
- Confirmed big spillover cases:
  - Block 4 en id "1" — ~2,500 chars (Rebbe niggun story)
  - Block 16 en id "3" — ~1,700 chars (Rebbe of Radomsk)
- Tune the column-capacity constant empirically: after initial implementation, render a couple of test builds with different constants and pick the value that produces visual balance (roughly half of the apparatus region per column before spillover kicks in).

### 3. Implement Path A (Python pre-partition)

Extend `python/convert.py`:

1. Add a char-capacity constant near the top of the file (`COL_CAPACITY_CHARS = 900` or similar). Document the calibration reasoning in a comment.
2. Refactor the note-emission section: for each block, instead of emitting `#fn[body]` / `#en[body]` inline, compute a per-stream plan:
   - `fn_col[]` = leading footnote bodies whose cumulative chars ≤ capacity.
   - `fn_spill[]` = remaining footnote bodies.
   - Same for endnotes.
3. Emit THREE calls per block (where each is non-empty):
   - `#fn-col[ids, bodies]` — right column content.
   - `#en-col[ids, bodies]` — left column content.
   - `#spillover[fn: [...], en: [...]]` — full-width row, fn overflow first then en overflow.
4. If a single note body exceeds capacity alone (e.g., block 16 en #3), it counts as zero-into-col and all-into-spillover for that block. Do NOT truncate — the spillover absorbs the full text.

### 4. Extend the Typst template

In `typst/template.typ`:

1. Replace the inline `#fn` / `#en` emitter (which was the M1 footnote-query pattern) with three wrapper functions `#fn-col`, `#en-col`, `#spillover`. These emit the appropriate `footnote` calls tagged with additional `metadata()` (`"fn-col"`, `"en-col"`, `"fn-spill"`, `"en-spill"`) so the page footer can partition them into three visual regions.
2. Extend the `page(footer: context {...})` rendering logic to, after rendering the 2-col grid, check whether any `"fn-spill"` or `"en-spill"` notes are present for this render page. If so, emit a third row: a single full-width block in commentary type (PFT_Vilna 9pt), fn-spill first then en-spill.
3. Increase `margin: bottom` as needed to accommodate 3-row apparatus (bottom margin ≈ 9-10cm on pages with spillover). Note: margin is set at page-run granularity, so expanding it affects all pages — verify body-text position does NOT shift on non-spillover pages (VAL-M2-010). If it does, consider a `page(margin: (bottom: ...))` conditional at chapter level or accept modest body-end variation within the 2pt tolerance.

### 5. Verify + record baselines

- Full build: `test` command from services.yaml.
- Cross-verification per spillover page: for each page with a `#spillover` emission, confirm the col+spillover ids union equals the body-referenced ids set (VAL-M2-009).
- Block 4 en #1 and Block 16 en #3 render full on single pages each (VAL-M2-011 + VAL-M2-004).
- Audit score does not regress from M1 beyond 1-point noise tolerance (VAL-M2-006, delta-based). See current validation-contract.md text.
- Update `validation-state.json::baselines.m2` = {pdf_page_count, audit_score, build_time_sec}. The file lives in your mission directory at `C:\Users\Main\.factory\missions\<mission-id>\validation-state.json`, NOT in the repo's `.factory/`. Use atomic read → mutate → write.

### 6. Self-verify every VAL-M2-* assertion

Per the contract. Use pypdf, book.typ parsing, PIL. Fix anything that fails before handoff.

### 7. Commit + hand off.

Single atomic commit for the feature.

## Example Handoff

```
{
  "featureId": "m2-spillover-implementation",
  "successState": "success",
  "whatWasDone": "Added COL_CAPACITY_CHARS=850 partitioning in convert.py. Emits #fn-col / #en-col / #spillover per block. Template renders a full-width 3rd row below the 2-col grid when spillover is non-empty. Bottom margin increased to 9cm on pages with spillover via state-based conditional; body-text position stable within 1pt on non-spillover pages. Block 4 en #1 + Block 16 en #3 both render on single pages with spillover.",
  "assertionsVerified": [
    {"id": "VAL-M2-001", "status": "passed", "evidence": "clean build, no warnings"},
    {"id": "VAL-M2-004", "status": "passed", "evidence": "Radomsk endnote spans left-col + spillover on page 14; full text present via pypdf"},
    {"id": "VAL-M2-006", "status": "passed", "evidence": "M2 score 65.3 vs baselines.m1.audit_score 66.0 (delta -0.7, within 1.0 tolerance)"},
    ...
  ],
  "baselinesWritten": {
    "baselines.m2.pdf_page_count": 18,
    "baselines.m2.audit_score": 56.2,
    "baselines.m2.build_time_sec": 0.44
  },
  "filesChanged": ["python/convert.py", "typst/template.typ"],
  "discoveredIssues": [],
  "whatWasLeftUndone": [],
  "notesForNextWorker": "COL_CAPACITY_CHARS=850 was empirically chosen — at 900 the apparatus was slightly too dense, at 800 too many pages unnecessarily triggered spillover. M3 ornament placement doesn't interact with the apparatus, so spillover pages + ornament pages are disjoint (verified by JSON block adjacency)."
}
```

## When to Return to Orchestrator

- **M1 baselines not recorded** — cannot proceed without `baselines.m1.pdf_page_count` and `.audit_score`.
- **Score improvement plateau below 55** — if even with optimal spillover tuning the audit score stays at ~52-54, there may be a contract-level issue (audit weights, alignment — see VAL-CROSS-010) that's outside this feature's scope.
- **A single note body is so huge it overflows a full PDF page** (theoretically possible but not actually true for this corpus). Would require a policy decision.
- **Typst compilation becomes non-deterministic** after the change — could indicate introspection non-convergence from the extra state layer.
