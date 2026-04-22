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

## Isolation strategy

Per-validator-session isolation:

- Each validator session begins by ensuring the sandbox is on the correct commit (ssh + `git rev-parse HEAD`).
- `rm -rf build ~/.cache/typst` before rebuild to avoid stale-artefact contamination (VAL-CROSS-011).
- Validators may append synthesis state to `.factory/validation/<milestone>/...` but must NOT modify source files, `build/` contents of other validator sessions, or `reference_scans/`.

## Runtime notes (populated by validators during execution)

*(This section is updated by user-testing-validator as it learns new things.)*
