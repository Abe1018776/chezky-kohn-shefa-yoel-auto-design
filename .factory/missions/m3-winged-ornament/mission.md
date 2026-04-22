# Mission M3 — Winged-cherub end-of-chapter ornament

## Goal

Replace the current `— ∞ —` placeholder ornament (used on end-of-chapter
pages and triggered by JSON blocks whose text is `"*"`) with a proper
winged-cherub glyph that matches the reference scans.

Appears on: last page of each chapter. In the reference sample, that is
pages 113 (end of פרק א), 118 (end of פרק ב), 122 (end of פרק ג).

## Visual reference

- `reference_scans/page_113.png` — single winged glyph centered between the
  last body paragraph and the start of the notes zone.
- `reference_scans/page_118.png` — same glyph, different context.
- `reference_scans/page_122.png` — same glyph, final chapter.

The glyph in the reference looks like a stylised winged seraph (outspread
wings with a small central body), horizontally centered, roughly 14mm wide,
in the same ink color as body text.

## Options

### Option A — Embed an SVG asset

1. Create / commission a single SVG asset, e.g. `typst/assets/ornament.svg`.
2. In `template.typ`, replace the current `ornament()` function body with
   `image("/typst/assets/ornament.svg", width: 14mm)` wrapped in an
   `align(center)`.

### Option B — Use a Unicode glyph from a symbol font

Some Hebrew-tradition display fonts include ornament / fleuron glyphs.
Inspect `typst/fonts/shefa.ttf` and `typst/fonts/PFT_Frank.ttf` for an
angel / cherub / fleuron codepoint; if present, emit it directly.

### Option C — Reconstruct from font outlines

If no suitable glyph is present, extract wing-like curves from an existing
font (e.g. a flourish in Drogolin) and composite via Typst's `path()` +
`place()` primitives.

**Recommended path**: A (SVG asset) — cleanest, font-independent, and the
exact shape is guaranteed to match.

## Acceptance

- All three end-of-chapter pages (the pages where JSON block text equals
  `"*"`) display the new winged ornament.
- The ornament is horizontally centered, approx 10–16mm wide.
- The ornament does not appear on any page that is not the last of a
  chapter.
- Rendering time remains < 2s.
