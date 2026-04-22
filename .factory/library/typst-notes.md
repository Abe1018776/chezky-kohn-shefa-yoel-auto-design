# Typst 0.14.2 — Notes apparatus design notes

Reference for workers implementing the two-stream note apparatus (M1)
and the spillover extension (M2). Consolidates the research findings
and known quirks from the Phase-2 investigation.

---

## The core constraint

Typst 0.14.2's `footnote.entry.separator` slot evaluates with
`here().page()` returning the DEFINITION page (page 1), not the render
page. This breaks any design that tries to inspect or group per-page
notes inside the separator.

**Evidence:** prior empirical probe in the sandbox confirmed
`here().page()` always returns 1 inside a
`set footnote.entry(separator: context { ... })` slot. `locate()` in
0.14 only accepts element selectors (not positions / page numbers);
`counter(page).get()` also resolves against the definition page.

## The supported pattern

```typst
// Suppress native apparatus entirely
#set footnote.entry(separator: none, clearance: 0pt, gap: 0pt, indent: 0pt)
#show footnote.entry: none

// Per-stream tag via metadata() survives query()
#let fn(body) = footnote[#metadata("fn") #body]   // right column — מקור השפע
#let en(body) = footnote[#metadata("en") #body]   // left column  — צינור השפע

// Hebrew letter numbering helper (existing in template.typ)
#let heb(n) = numbering("א", n)

// The apparatus lives in the page footer, which evaluates per rendered page.
// `here().page()` INSIDE page(footer: context { ... }) returns the RENDER page.
#set page(
  margin: (bottom: 7cm, top: 2cm, x: 2cm),  // pre-reserve generous bottom
  footer: context {
    let pg = here().page()
    let notes-here = query(footnote).filter(n => n.location().page() == pg)
    let is-fn(n) = n.body.children.first().value == "fn"
    let fns = notes-here.filter(is-fn)
    let ens = notes-here.filter(n => not is-fn(n))

    // Case A: footnotes only → single centered header
    if ens.len() == 0 and fns.len() > 0 {
      align(center, text(font: "Drogolin", size: 10pt)[─── מקור השפע ───])
      v(0.4em)
      render-stream(fns)
    }
    // Case B: both streams → 2-col grid with both headers
    else if ens.len() > 0 {
      line(length: 40%, stroke: 0.4pt)
      v(0.4em)
      grid(
        columns: (1fr, 0.5em, 1fr),
        align: (right, center, left),
        [#align(center)[מקור השפע]], [], [#align(center)[צינור השפע]],
      )
      v(0.3em)
      grid(
        columns: (1fr, 0.5em, 1fr),
        align: (right, center, left),
        render-stream(fns), [], render-stream(ens),
      )
    }
  }
)
```

**Key caveats:**

1. **`here().page()` correctness** — empirically verified in 0.14.2
   inside `page(footer: context { ... })`. This is the whole basis of
   the design. Workers should commit a small probe to the template or
   a side-file to keep this fact visible.

2. **RTL column ordering** — inside `set text(dir: rtl)`, a
   `grid(columns: (1fr, 1fr))` places column-1 on the right. So "right
   column (מקור)" maps to grid cell 0 and "left column (צינור)" to
   grid cell 2 (with a 0.5em gutter cell in between). Verify by
   comparing against `reference_scans/page_105.png`.

3. **`metadata()` tagging** — `footnote[#metadata("fn") body]` puts a
   `metadata` element as the first child of `body`. The filter
   `n.body.children.first().value == "fn"` accesses it. Confirm the
   filter works — Typst's content model sometimes wraps bodies in
   implicit `paragraph` nodes, which may require
   `children.first().children.first()` or a recursive lookup.

4. **Body space is fixed** — `page(footer: ...)` + `show footnote.entry: none`
   means Typst does NOT dynamically reserve body space for notes. The
   apparatus lives in the FIXED bottom margin we pre-reserved (7cm). If
   notes overflow that margin, the footer content clips silently. This
   is why M2's spillover is needed AND why M2 pre-partitions notes in
   Python: the column capacity is fixed, so overflow must be routed by
   the converter, not by Typst.

5. **Per-chapter counter reset** is NOT automatic. Typst's
   `counter(footnote)` is global. Implement reset via either:
   - A `state("fn-by-chapter", (:))` dictionary keyed by chapter index,
     stepped inside `#fn` wrapper, read in the footer via
     `state.final(here())`.
   - A `counter` per chapter named dynamically, e.g.
     `counter("fn-ch-" + str(current_chapter))`.
   - Inside the footer's render loop, compute each note's label as
     `numbering("א", note_index_within_chapter_within_stream)` where
     the index is derived from counting prior notes of the same
     stream in the same chapter via `query(footnote).filter(...)`.

## Recommended empirical probes (run BEFORE committing the apparatus rewrite)

All probes run on the sandbox. Each takes a few seconds.

### Probe 1 — `here().page()` in page footer

```typst
// probe1.typ
#set page(
  width: 100mm, height: 40mm, margin: 1cm,
  footer: context { text(size: 8pt)[footer-page: #here().page()] },
)
body1 #footnote[ref on page 1]
#pagebreak()
body2 #footnote[ref on page 2]
#pagebreak()
body3 #footnote[ref on page 3]
```

Expected: the footer on page N reads "footer-page: N", not "footer-page: 1".

### Probe 2 — RTL grid column order

```typst
// probe2.typ
#set page(width: 100mm, height: 30mm, margin: 5mm)
#set text(dir: rtl, font: "PFT_Frank")
#grid(
  columns: (1fr, 1fr),
  [RIGHT-cell], [LEFT-cell],
)
```

Visually inspect the output PNG: "RIGHT-cell" must appear on the RIGHT and "LEFT-cell" on the LEFT.

### Probe 3 — `metadata()` survives `query()`

```typst
// probe3.typ
#footnote[#metadata("fn") first one]
#footnote[#metadata("en") second one]
#context {
  let ns = query(footnote)
  text(size: 8pt)[
    #for n in ns [
      tag=#n.body.children.first().value body=#n.body.children.last().value \
    ]
  ]
}
```

Expected output line: `tag=fn body=...` and `tag=en body=...`. If the filter returns the wrong elements, walk deeper into the children tree.

## Implementation checklist for M1 workers

- [ ] Run the 3 probes; document results in this file (append a "Probe results" section).
- [ ] Drop the `set footnote.entry(separator: ...)` block; replace with zero + hidden via `show footnote.entry: none`.
- [ ] Define `#fn` / `#en` wrappers with `metadata()` tags.
- [ ] Build the `context {...}` footer partitioning + rendering logic.
- [ ] Implement per-chapter-per-stream numbering (Hebrew letters).
- [ ] Pre-reserve `page(margin: (bottom: 7cm))` (tune empirically — must comfortably hold ≥10-line 2-col apparatus at commentary size).
- [ ] Commit a font fallback for Noto Serif Hebrew so `warning: unknown font` stops.
- [ ] Emit `build/notes.json` for validators — each note record: `{stream: "fn"|"en", chapter: N, page: N, index_within_chapter_stream: N, marker: "[א]", body_first_25: "..."}`.

## Open questions (for workers — answer via probes or leave as known-limitations)

- **Introspection convergence stability** — when the apparatus gets dense (many notes on a page with spillover), does Typst's multi-pass introspection converge deterministically? Test with a full-book build and `sha256sum` twice.
- **Multi-page footnote** — if a single note body is so long it would naturally break across pages, does `n.location().page()` return the page of the SUPERSCRIPT or the START of the body? (Answer should be superscript page; confirm.)
- **Interaction with `set footnote.entry(separator: none, clearance: 0pt, gap: 0pt)`** — does Typst still reserve a minimum apparatus clearance? Test by stacking enough body content that a few lines would fit without the apparatus and observe whether those lines materialize.
