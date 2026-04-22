# AGENTS.md — Mission M3

## Build

Same as M1 / M2.

## Testing & Validation Guidance

- For A2, open each `build/page-*.png`, look in the region
  `[page-width 10%..90%] × [page-height 55%..70%]` and count contiguous
  dark-pixel blobs. Alternatively, run an OCR-free dark-pixel scan with
  Pillow.
- For A3, render ornament pages at 300dpi and compare the cropped region to
  the reference scan crops of pages 113 / 118 / 122.
- For A4, compute the bounding box of the dark pixels in the ornament region
  and check the box midpoint is within 2mm of page center.

## Where the ornament is emitted

`typst/template.typ` → `#let ornament() = ...` ; currently:

```typst
#let ornament() = {
  v(1fr)
  align(center)[
    #text(size: 22pt, fill: luma(30%))[
      #sym.dash.em#h(2pt)#sym.infinity#h(2pt)#sym.dash.em
    ]
  ]
  v(1fr)
}
```

The JSON path: `docx_content[i].text == "*"` → `convert.py` emits
`#ornament()` inline.
