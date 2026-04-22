---
name: ornament-worker
description: Implements the winged-cherub end-of-chapter ornament (M3). Invoke for features that create typst/assets/ornament.svg, wire it into the template's ornament() function, and commit audit/blob_scan.py.
---

# Ornament Worker

You implement the Phase-2 M3 milestone: the winged-cherub glyph that
appears on end-of-chapter pages. This is the smallest of the three
milestones in implementation scope, but it must be visually precise
and must not regress M1 or M2.

## Required knowledge

Before starting, READ:

1. Your mission directory's `mission.md`
2. `validation-contract.md` — especially M3 section (VAL-M3-001..007)
3. `AGENTS.md` (operational boundaries)
4. `.factory/services.yaml`
5. `.factory/library/architecture.md`
6. `.factory/missions/m3-winged-ornament/mission.md` — authoritative ornament design spec (Option A = SVG asset, recommended)
7. The reference scans: `reference_scans/page_113.png`, `reference_scans/page_118.png`, `reference_scans/page_122.png` — the actual visual target for the ornament
8. The current `ornament()` function in `typst/template.typ` (placeholder `— ∞ —` that you're replacing)

## Work procedure

### 1. Sync + verify M1 + M2 green

- SSH to sandbox; confirm HEAD.
- Run `test` command; confirm all M1 and M2 assertions still pass.
- Read `baselines.m2` from validation-state.json — your score must not fall below it.

### 2. Design the SVG

Reference glyph: a stylised winged seraph (outspread wings with small central body), about 14mm wide at native size. Inspect the reference scans closely.

Constraints:
- Width ≈ 14mm (within [10, 16] mm range).
- Horizontally centered in the SVG viewBox.
- Pure vector (no embedded bitmaps).
- Single color — matches body-text ink (black or near-black).
- Valid `<svg>` root with `viewBox="0 0 W H"`, `xmlns="http://www.w3.org/2000/svg"`.
- File size small (< 20KB; ideally < 5KB).

If commissioning a detailed ornament is out of scope, a clean stylized approximation using SVG `<path>` primitives is acceptable — the reference scan glyph is itself stylized. Prioritize: (i) recognizable as wings + central body, (ii) horizontally symmetric, (iii) visual weight comparable to surrounding text.

Place the finished file at `typst/assets/ornament.svg`. Create the directory if it doesn't exist.

### 3. Wire into template

In `typst/template.typ`, find the `ornament()` function (currently emits `#sym.dash.em#h(2pt)#sym.infinity#h(2pt)#sym.dash.em`). Replace its body with:

```typst
#let ornament() = {
  v(1fr)
  align(center, image("/typst/assets/ornament.svg", width: 14mm))
  v(1fr)
}
```

If the `v(1fr)` flex-spacing interacts badly with M1/M2's bottom-margin changes, use explicit `v(8mm)` above and below instead. Verify by building.

### 4. Commit audit/blob_scan.py

Create a short helper at `audit/blob_scan.py` that scans a PNG's mid-band and reports ornament-shaped blobs. Minimal signature:

```python
# audit/blob_scan.py
import sys
from PIL import Image

BAND_X = (0.10, 0.90)   # horizontal range to scan
BAND_Y = (0.55, 0.70)   # vertical range
MIN_WIDTH_MM = 10
MAX_ASPECT = 4.0
MIN_ASPECT = 2.0

def scan(png_path):
    """Return list of {x0,y0,x1,y1,width_mm,height_mm,aspect} dicts."""
    # Implementation: threshold to binary, flood-fill blobs in the band,
    # filter by size + aspect ratio, convert pixels to mm using known
    # page width 170mm.
    ...

if __name__ == "__main__":
    for p in sys.argv[1:]:
        hits = scan(p)
        print(f"{p}: {len(hits)} ornament-shaped blob(s)")
        for h in hits:
            print(f"  {h}")
```

Commit it. Validators will call it to verify VAL-M3-003 / VAL-M3-004.

### 5. Build, measure, verify

- Full pipeline build.
- Identify the three ornament pages dynamically:
  ```python
  # Python, on sandbox
  import pypdf
  r = pypdf.PdfReader('build/book.pdf')
  chapter_titles = [...]  # extract vowelised titles from JSON chapter_title blocks
  # for each title, find its page in the PDF text; ornament page = that page - 1
  ```
- For each ornament page: measure bbox width + centroid via `audit/blob_scan.py`. Confirm width in [10,16]mm and centroid within 2mm of 85mm midline.
- For every non-ornament page: run blob_scan and confirm zero ornament-shaped blobs.
- Score ≥ `baselines.m2.audit_score`.
- Build time < 2s.

### 6. Self-verify every VAL-M3-* assertion + replay M1/M2 assertions to confirm no regression.

### 7. Commit + hand off.

## Example Handoff

```
{
  "featureId": "m3-ornament-svg",
  "successState": "success",
  "whatWasDone": "Created typst/assets/ornament.svg (4.8 KB, stylized winged seraph, 14mm native width). Updated template.typ ornament() to use image() instead of em-dash+infinity placeholder. Committed audit/blob_scan.py with the PIL-based ornament detector. Ornament renders on pages 7, 14, 18 (= last page of chapters 1, 2, 3) matching the computed expected set. Widths 14.1 / 14.0 / 14.2 mm; centroid offsets 0.8 / 1.1 / 0.6 mm.",
  "assertionsVerified": [
    {"id": "VAL-M3-001", "status": "passed", "evidence": "full pipeline clean; M1+M2 replay all green; audit 56.9 >= M2 baseline 56.2"},
    {"id": "VAL-M3-003", "status": "passed", "evidence": "blob scan hits = {7, 14, 18}; computed expected = {7, 14, 18}; symmetric diff = empty"},
    {"id": "VAL-M3-004", "status": "passed", "evidence": "blob scan on 15 non-ornament pages: 0 ornament-shaped blobs"},
    ...
  ],
  "filesChanged": [
    "typst/assets/ornament.svg (new)",
    "typst/template.typ (ornament() function)",
    "audit/blob_scan.py (new)"
  ],
  "discoveredIssues": [],
  "whatWasLeftUndone": [],
  "notesForNextWorker": "Blob_scan.py uses a simple threshold at luma=128; it works reliably here because body text is far from the mid-band on ornament pages (which have short tails). On chapter-opener pages, body text in the mid-band is text-shaped (aspect < 2:1 typically) and gets filtered out. If future pages push denser content into 55-70% y-band, the detector may need a shape-aware filter upgrade."
}
```

## When to Return to Orchestrator

- **SVG design too subjective** — if you're uncertain the glyph visually matches the reference to stakeholder satisfaction, commit a good-faith approximation and flag in your handoff for orchestrator review + user input.
- **blob_scan false-positives on body text** — if non-ornament pages consistently register ornament-shaped blobs, the body content is colliding with the detection band. Orchestrator decides: tighten the shape filter, shift the band, or re-spec VAL-M3-004 tolerance.
- **Audit score regresses below M2 baseline** — the SVG should not tank the score. If it does, something else is wrong (pagination shift, SVG rasterizing at low DPI, etc.).
