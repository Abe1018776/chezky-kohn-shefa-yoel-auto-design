# AGENTS.md — Mission M1

## Build

```bash
cd /home/factory-user/chezky-kohn-shefa-yoel-auto-design
python3 python/convert.py
~/.local/bin/typst compile --root . --font-path typst/fonts build/book.typ build/book.pdf
~/.local/bin/typst compile --root . --font-path typst/fonts build/book.typ build/page-{n}.png --ppi 120 --format png
```

## Testing & Validation Guidance

This mission is verified visually + via the `audit/image_diff.py` harness.

- To test a specific assertion, first rebuild the PDF and PNGs using the
  command above.
- For visual assertions (A2, A3, A4), open the corresponding PNG in
  `build/page-*.png` and inspect the notes zone at the bottom of the page.
- For A5, count pages via `~/.local/bin/typst compile` stdout or a
  `len(sorted(Path('build').glob('page-*.png')))` check.
- For A6, run `python3 audit/image_diff.py` and parse the "Average score"
  line of `build/audit_report.md`.

## Feature surfaces

- `typst/template.typ` — layout DSL
- `python/convert.py` — JSON→Typst bridge
- `audit/image_diff.py` — validation script

## Data mapping (from `source_uploads/docx_content_with_notes.json`)

Blocks with endnotes: 4, 6, 16, 18, 31, 35, 37, 48, 50
Blocks with footnotes only (no endnotes): 8, 10, 12, 14, 20, 22, 24, 29, 33,
  42, 44, 46
