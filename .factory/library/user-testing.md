# User Testing Surface

How validators exercise the validation contract assertions, and which tools apply where.

---

## Surfaces

There is ONE testable surface: the build output artefacts.

- `build/book.pdf` — final typeset PDF. Text extraction via `pypdf`.
- `build/page-{n}.png` — per-page PNG raster at 120 ppi. Visual inspection + PIL pixel measurement.
- `build/book.typ` — emitted Typst source. Useful for grep-based verification of emitter-side invariants (e.g. `#fn-col` call ordering).
- `build/audit_report.md` — scored markdown report produced by `audit/image_diff.py`. Contains per-page structural-similarity score + heuristic flags (notes-hdr, cartouche).
- `build/notes.json` — (M1+) side-artefact emitted by Typst `query(footnote.entry)`, per-note metadata. Used by validators to bypass pypdf RTL flakiness on marker-based assertions.

Optional sibling artefacts workers may produce for assertion testability:

- `build/book.plain.txt` — Typst-emitted plaintext reading-order dump, used when pypdf RTL extraction proves unreliable.
- `audit/blob_scan.py` — reusable PIL helper for detecting ornament-shape blobs in a specified band of a PNG (committed as part of M3).
- `audit/alignment.json` — if the generated page count diverges from 20 reference scans, this file maps generated page → reference scan (committed as part of M1 feature `m1-audit-pagination-alignment`).

## Required tools for validators

- `agent-browser` — NOT applicable. No web surface.
- `tuistory` — NOT applicable. No TUI.
- `shell` — applicable. SSH to `sefer-design` per the recipe in AGENTS.md.
- `pypdf` — applicable. For all text-based assertions. Note Hebrew RTL extraction quirks (see AGENTS.md fallback).
- `visual-inspection` (Read tool on synced PNGs) — applicable. PNGs must first be synced from sandbox to Windows host (see AGENTS.md sync recipe). If sync proves unreliable, fall back to on-sandbox PIL measurements returning textual bbox + pixel-row reports.
- `PIL` — applicable. Used for blob detection, pixel-row/column measurement, luma sampling. Runs on the sandbox.

## Resource cost classification per surface

- `build/book.pdf` extraction: CHEAP (< 100ms per full extraction).
- `build/page-{n}.png` PIL scan: CHEAP (< 50ms per page for simple bbox detection).
- Full pipeline rebuild: CHEAP (< 2s end-to-end).
- Audit run (`image_diff.py`): MEDIUM (several seconds — loops over 10-24 pages × 20 reference scans, computes SSIM + pHash).
- Visual inspection over Read tool on PNG: CHEAP per-call but requires file sync from sandbox (5-10s overhead for an entire build/ of ~20 PNGs via base64-over-ssh).

## Concurrency

1 (serial). The pipeline is SSH-bound — parallel builds on the same sandbox will collide on `build/`. Validators should run one assertion check at a time, or batch-read artefacts from a single completed build.

## Validation Concurrency

- Surface: `build-artifacts`
  - Max concurrent validators: `1`
  - Rationale: all assertions share the same sandbox repo and single `build/` output directory.

## Isolation strategy

Per-validator-session isolation:

- Each validator session begins by ensuring the sandbox is on the correct commit (ssh + `git rev-parse HEAD`).
- `rm -rf build ~/.cache/typst` before rebuild to avoid stale-artefact contamination (VAL-CROSS-011).
- Validators may append synthesis state to `.factory/validation/<milestone>/...` but must NOT modify source files, `build/` contents of other validator sessions, or `reference_scans/`.

## Runtime notes (populated by validators during execution)

- `pypdf` Hebrew extraction is unreliable for long RTL note bodies on this corpus; for note-presence/order assertions, prefer `build/book.plain.txt` and `build/notes.json` emitted via Typst query.
- In delegated validator sessions where destructive cleanup commands are denied, determinism/clean-build checks can still run using reversible moves of prior `build/` and cache directories into `/tmp` before rebuild.

## Subtitle sampling guidance

Subtitle right-alignment verification (VAL-M1-014 and any future
subtitle-style assertion) MUST sample via the `<subtitle-loc>` metadata
tag emitted by `subtitle()` in `typst/template.typ`, **not** via fixed-Y
ROI crops. The opener-page layout (cartouche → chapter_title →
subtitle) shifts the subtitle's y-coordinate below where a body-page
subtitle would sit; a body-page-calibrated fixed-Y crop will land on
the centred cartouche on chapter-opener pages (pages 1, 7, 12 in the
current build), producing a false "318–339 px right-edge gap" that is
actually the cartouche-to-page-edge gap, not the subtitle-to-page-edge
gap.

Recipe:

```
# 1) Emit/refresh build artefacts
rm -rf build && mkdir build
python3 python/convert.py
SOURCE_DATE_EPOCH=1704067200 ~/.local/bin/typst compile \
    --root . --font-path typst/fonts build/book.typ build/book.pdf
SOURCE_DATE_EPOCH=1704067200 ~/.local/bin/typst compile \
    --root . --font-path typst/fonts build/book.typ \
    'build/page-{n}.png' --ppi 120 --format png

# 2) Query the subtitle locations
~/.local/bin/typst query --root . --font-path typst/fonts \
    --format json build/book.typ '<subtitle-loc>' --field value
```

Each record contains `{index_in_stream, page, x_pt, y_pt}`. Convert
`y_pt` to PNG pixels with the actual page dimensions (page height
240 mm ⇒ `y_px = y_pt * (image_height_px / (240 * 72 / 25.4))`), then
crop a narrow strip at that y to measure luma / right-edge gap / glyph
height. The subtitle text-block right edge should sit within
`(page_right_margin + small slack)` pixels of the PNG right edge. The
page geometry is `inside: 25mm, outside: 20mm` — in a RTL book the
binding (inside) alternates between the right and left physical edges
by parity, so the empirical right-edge gap alternates between
~96 px (20 mm outside margin @ 120 ppi) and ~120 px (25 mm inside
margin @ 120 ppi). A reasonable threshold is ≤ 130 px; anything
substantially larger (e.g. 300+ px, as in the original VAL-M1-014
false-alarm report) indicates the ROI landed on a non-subtitle
element (typically the centred cartouche on opener pages).

## Flow Validator Guidance: build-artifacts

- Isolation boundary: all commands must run only inside `/home/factory-user/chezky-kohn-shefa-yoel-auto-design` on `sefer-design`.
- Do not edit source files; only generate/inspect `build/*` artefacts and write the assigned flow report JSON.
- Use the SSH recipe from mission `AGENTS.md`; do not open ports or run background services.
- Keep execution serial (no parallel builds). If a clean rebuild is needed, use `rm -rf build` before running the pipeline.
