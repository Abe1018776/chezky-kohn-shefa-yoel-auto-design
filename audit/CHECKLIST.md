# Audit Checklist — Hard Requirements

The 4 hard requirements from the sefer spec, each with a specific test and the
reference page that demonstrates it.

| # | Requirement | Reference page(s) | Verification |
|---|---|---|---|
| 1 | Header: `שפע` bold, shaar name, `שלמה`, folio letter in gematria | all content pages | Visual diff top strip only (`diff_headers.py`) |
| 2 | Chapter cartouche: oval frame with `פרק X`, vowelised title below, pushes body ~40% down the page | 105, 114, 119 | Geometry check: body text baseline should be ≥ 40% from top on opener pages |
| 3 | Note apparatus: 2 columns (RTL), מקור השפע right, צינור השפע left, independently typeset heights; spillover zone full-width beneath | 105, 109, 113, 117 | Per-page column count + header text occurrence |
| 4 | Footnote pinning: each call-out `[X]` inside body text on page N has its note body rendered on the same page N (no cross-page notes) | all pages with notes | Structural: walk PDF, cross-reference call-out page with note page |

Secondary requirements (not strictly hard, but tracked):
- Start-of-chapter adds a new page even if previous was nearly empty
- Chapter-end ornament appears only on last page of chapter (113, 118, 122)
- No orphan lines at top/bottom of pages
- Subtitle never orphaned — always followed by at least 2 body lines on same page

## How to run the audit

```bash
# Image-diff the generated PDF against reference scans:
python3 audit/image_diff.py \
    --output build/book.pdf \
    --reference reference_scans \
    --report build/audit_report.md
```

The report writes:
- Per-page SSIM, phash distance, and header-strip diff
- Checklist pass/fail per hard requirement
- Overall score (0..100)
