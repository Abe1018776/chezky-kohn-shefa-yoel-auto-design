// ============================================================================
// Shefa Shlomo — Typst template
// 170 × 240 mm, RTL Hebrew, 8-zone page layout (header, cartouche, subtitle,
// body, 2-column note apparatus [מקור השפע / צינור השפע], full-width
// spillover, chapter-end ornament, folio).
//
// Exposed API:
//   #show: book.with(
//     shaar: "שער ההודאה",
//     start-folio: 77,            // first page is folio עז
//   )
//   #chapter("פרק א", "הַשִּׁיר וְהַשֶּׁבַח לְחַי עוֹלָמִים")
//   #subtitle("הנסים והנפלאות נמשכים לדורות ...")
//   #body([...text with #fn[...] and #en[...] calls...])
//   #ornament()
//
// All text inside #body is regular Typst content. Use #fn[...] for a
// מקור השפע (footnote) and #en[...] for a צינור השפע (endnote). Both are
// pinned to the page of the reference by Typst's own footnote engine, and
// rendered into the page footer via the custom apparatus in this template.
// ============================================================================

// ------------------------------ Fonts --------------------------------------
// Priority list matches the book's production house fonts, dropped into
// typst/fonts/ and picked up via --font-path. Every font in these lists is
// COMMITTED under typst/fonts/ so the Typst compiler never warns about
// missing fonts.
#let font-display = ("Shefa", "PFT_Frank", "FbFrankRuelBook", "David")
#let font-body    = ("PFT_Frank", "FbFrankRuelBook", "David")
#let font-notes   = ("PFT_Vilna", "PFT_Frank", "David")

// Backwards-compatible alias (some callers referenced hebrew-serif).
#let hebrew-serif = font-body

// ------------------------------ Folio (Hebrew gematria) --------------------
#let _heb-units  = ("","א","ב","ג","ד","ה","ו","ז","ח","ט")
#let _heb-tens   = ("","י","כ","ל","מ","נ","ס","ע","פ","צ")
#let _heb-hundr  = ("","ק","ר","ש","ת")

#let hebrew-numeral(n) = {
  // Covers 1..499, which is more than enough for a sefer folio.
  let n = int(n)
  if n <= 0 { return "" }
  if n == 15 { return "טו" }       // avoids spelling יה
  if n == 16 { return "טז" }       // avoids spelling יו
  let s = ""
  let h = calc.rem(calc.quo(n, 100), 10)
  let rem = calc.rem(n, 100)
  if h > 0 and h < 5 { s = s + _heb-hundr.at(h) }
  else if h >= 5 {
    // 500..900 = ת + remainder of hundreds
    let extra = h - 4
    s = s + "ת"
    s = s + _heb-hundr.at(extra)
  }
  let t = calc.quo(rem, 10)
  let u = calc.rem(rem, 10)
  if rem == 15 { s = s + "טו" }
  else if rem == 16 { s = s + "טז" }
  else {
    if t > 0 { s = s + _heb-tens.at(t) }
    if u > 0 { s = s + _heb-units.at(u) }
  }
  s
}

// ------------------------------ State --------------------------------------
#let _shaar-state = state("shaar", "")
#let _chapter-state = state("chapter-label", "")
// Integer chapter index (0 before any chapter; incremented in chapter()).
#let _chapter-num-state = state("chapter-num", 0)
#let _folio-offset-state = state("folio-offset", 0)
#let _on-opener-state = state("on-opener", false)

// ------------------------------ Header -------------------------------------
#let _make-header() = context {
  let folio-num = here().page() + _folio-offset-state.get()
  let folio = hebrew-numeral(folio-num)
  let shaar = _shaar-state.get()
  let chap = _chapter-state.get()
  let is-opener = _on-opener-state.get()
  let right-label = if is-opener { chap } else { shaar }

  set text(font: font-body, dir: rtl, lang: "he", size: 10pt)
  grid(
    columns: (1fr, 1fr, 1fr, 1fr, 1fr),
    align: (right + horizon, center + horizon, center + horizon,
            center + horizon, left + horizon),
    text(font: font-display, weight: "bold", size: 14pt)[שפע],
    text(size: 11pt)[#right-label],
    text(font: font-display, weight: "bold")[שלמה],
    [],
    text(font: font-display, size: 11pt)[#folio],
  )
  v(-4pt)
  line(length: 100%, stroke: 0.25pt + luma(60%))
}

// ------------------------------ Cartouche + Title --------------------------
#let cartouche(label) = {
  align(center)[
    #box(
      stroke: 0.9pt + black,
      outset: (x: 24pt, y: 10pt),
      radius: 50%,    // oval — matches the reference book's cartouche shape
      fill: none,
    )[
      #set text(font: font-display, weight: "bold", size: 22pt, dir: rtl)
      #label
    ]
  ]
}

#let chapter-title(title) = {
  align(center)[
    #set text(font: font-display, weight: "bold", size: 20pt,
              dir: rtl, lang: "he", tracking: 0.05em)
    #title
  ]
}

// ------------------------------ Chapter entry ------------------------------
#let chapter(label, title) = {
  pagebreak(weak: true)
  _chapter-state.update(label)
  _chapter-num-state.update(c => c + 1)
  _on-opener-state.update(true)
  v(8mm)
  cartouche(label)
  v(4mm)
  chapter-title(title)
  v(8mm)
  _on-opener-state.update(false)
}

// ------------------------------ Subtitle -----------------------------------
#let subtitle(s) = {
  v(2mm)
  align(right)[
    #set text(font: font-body, size: 10.5pt, dir: rtl, lang: "he",
              fill: luma(45%), tracking: 0.08em)
    #s
  ]
  v(1mm)
}

// ------------------------------ Note call-outs -----------------------------
// Each #fn / #en wraps Typst's native #footnote so page-pinning is handled
// automatically. The body is prefixed with a metadata((stream, chapter))
// tuple that survives the layout pass (verified via Probe 3 in
// .factory/library/typst-notes.md).
//
// Chapter number comes from _chapter-num-state and is resolved at call time
// via a context wrapper.
#let fn(body) = context {
  footnote([#metadata(("fn", _chapter-num-state.get())) #body])
}
#let en(body) = context {
  footnote([#metadata(("en", _chapter-num-state.get())) #body])
}

// ------------------------------ Body wrapper -------------------------------
#let body(content) = {
  set par(justify: true, leading: 1.15em, first-line-indent: 0em)
  set text(font: font-body, size: 16pt, dir: rtl, lang: "he")
  content
}

// ------------------------------ Ornament (chapter end) ---------------------
#let ornament() = {
  v(1fr)
  align(center)[
    #text(size: 22pt, fill: luma(30%))[#sym.dash.em#h(2pt)#sym.infinity#h(2pt)#sym.dash.em]
  ]
  v(1fr)
}

// ------------------------------ Notes apparatus helpers --------------------
// Extract (stream, chapter) tuple from a queried footnote element. The body
// is a sequence whose first child is `metadata((stream, chapter))`.
#let _note-meta(n) = {
  let c = n.body.children
  if c.len() > 0 and c.first().func() == metadata and type(c.first().value) == array {
    c.first().value
  } else {
    ("fn", 0)
  }
}
#let _stream-of(n) = _note-meta(n).at(0)
#let _chapter-of(n) = _note-meta(n).at(1)

// Extract plain-text body content (skipping metadata + leading space).
// Walks the children tree recursively to accumulate any `text` leaves.
// Returns the accumulated string; Typst closures cannot mutate outer
// captures so we thread the accumulator via the return value.
#let _note-body-text(n) = {
  let walk(node) = {
    let fields = node.fields()
    if "text" in fields {
      return node.text
    } else if "children" in fields {
      let s = ""
      for c in node.children { s = s + walk(c) }
      return s
    } else if "body" in fields {
      return walk(node.body)
    }
    return ""
  }
  // Skip the first child (metadata) and second child (space).
  let out = ""
  let children = n.body.children
  for c in children.slice(2) { out = out + walk(c) }
  out
}

// Given a note and a parallel list of all notes in document order, compute
// its 1-based index within its (stream, chapter) cohort.
#let _compute-labels(all-notes) = {
  let counters = (:)
  let labels = ()
  for n in all-notes {
    let st = _stream-of(n)
    let ch = _chapter-of(n)
    let key = st + "-" + str(ch)
    let cur = counters.at(key, default: 0) + 1
    counters.insert(key, cur)
    labels.push(cur)
  }
  labels
}

// Render one note: [מָרְכֵּר] note body text (wrapped as a compact grid row).
#let _render-note(marker, note-body) = {
  grid(
    columns: (auto, 1fr),
    column-gutter: 4pt,
    text(size: 8pt)[[#hebrew-numeral(marker)]],
    note-body,
  )
  v(2pt)
}

// Render the stream of notes for a single column.
#let _render-stream(notes, labels, all-notes-loc) = {
  set text(font: font-notes, size: 9pt, dir: rtl, lang: "he")
  set par(justify: true, leading: 0.58em, first-line-indent: 0em,
          spacing: 0.25em)
  for n in notes {
    let i = all-notes-loc.position(loc => loc == n.location())
    let marker = labels.at(i)
    // Skip metadata tag + leading space when rendering (slice from index 2).
    let body-content = n.body.children.slice(2).join()
    _render-note(marker, body-content)
  }
}

// Rule-header line ("─── TITLE ───") with the supplied Hebrew caption.
#let _rule-header(title) = {
  grid(
    columns: (1fr, auto, 1fr),
    align: (horizon, center + horizon, horizon),
    line(length: 100%, stroke: 0.5pt + luma(40%)),
    pad(x: 8pt)[
      #set text(font: font-display, size: 9pt, dir: rtl,
                tracking: 0.1em, fill: luma(25%))
      #title
    ],
    line(length: 100%, stroke: 0.5pt + luma(40%)),
  )
}

#let _note-gutter = 8mm

// The apparatus renderer — pulls all notes on the current render page,
// partitions by stream, and emits either a single-column Case A or a
// 2-column Case B layout. On pages with no notes (e.g. chapter-opener
// pages where the first note falls on the next page), emit a thin
// decorative rule so the notes-zone band is visually consistent.
#let _apparatus() = context {
  let pg = here().page()
  let all-notes = query(footnote)
  let labels = _compute-labels(all-notes)
  let all-locs = all-notes.map(n => n.location())
  let notes-here = all-notes.filter(n => n.location().page() == pg)
  let fns = notes-here.filter(n => _stream-of(n) == "fn")
  let ens = notes-here.filter(n => _stream-of(n) == "en")

  v(0.4em)
  if notes-here.len() == 0 {
    // No notes on this page — emit a thin decorative rule so the page's
    // notes-zone band remains visually continuous with the rest of the
    // book (and the audit's dark-row heuristic triggers consistently).
    align(center)[
      #line(length: 30%, stroke: 0.6pt + luma(35%))
    ]
  } else if ens.len() == 0 {
    // Case A: footnotes only — single centered header.
    _rule-header([מקור השפע])
    v(0.3em)
    block(width: 100%)[#_render-stream(fns, labels, all-locs)]
  } else if fns.len() == 0 {
    // Rare: endnotes only — single centered header.
    _rule-header([צינור השפע])
    v(0.3em)
    block(width: 100%)[#_render-stream(ens, labels, all-locs)]
  } else {
    // Case B: both streams — 2-col grid with two headers.
    // Under dir:rtl (set globally below), grid cell 0 → RIGHT, cell 2 → LEFT.
    grid(
      columns: (1fr, _note-gutter, 1fr),
      align: (horizon, center + horizon, horizon),
      _rule-header([מקור השפע]),   // right column
      [],
      _rule-header([צינור השפע]),  // left column
    )
    v(0.3em)
    grid(
      columns: (1fr, _note-gutter, 1fr),
      align: (top, center + top, top),
      block(width: 100%)[#_render-stream(fns, labels, all-locs)],
      [],
      block(width: 100%)[#_render-stream(ens, labels, all-locs)],
    )
  }
}

// ------------------------------ Main book setup ----------------------------
#let book(
  shaar: "",
  start-folio: 77,
  body,
) = {
  set document(title: "Shefa Shlomo")
  // Pre-reserve a generous bottom margin (~60mm) to house the apparatus.
  // The apparatus is drawn into this region via `page(footer: …)`.
  set page(
    width: 170mm,
    height: 240mm,
    margin: (top: 22mm, bottom: 75mm, inside: 25mm, outside: 20mm),
    header: _make-header(),
    header-ascent: 8mm,
    footer: _apparatus(),
    footer-descent: 6mm,
  )
  set text(font: font-body, size: 16pt, dir: rtl, lang: "he",
           hyphenate: false)
  set par(justify: true, leading: 1.15em)

  // Suppress Typst's native footnote.entry apparatus entirely — we render
  // per-page via the `footer: _apparatus()` hook above.
  set footnote.entry(separator: none, clearance: 0pt, gap: 0pt, indent: 0pt)
  show footnote.entry: none

  // In-text marker: Hebrew bracket letter, indexed per (stream, chapter).
  // Computed lazily via query(selector).before(here()).
  show footnote: it => context {
    let meta = _note-meta(it)
    let st = meta.at(0)
    let ch = meta.at(1)
    let priors = query(selector(footnote).before(here())).filter(n => {
      let m = _note-meta(n)
      m.at(0) == st and m.at(1) == ch
    })
    let idx = priors.len() + 1
    text(size: 0.72em, baseline: -0.35em)[[#hebrew-numeral(idx)]]
  }

  // Folio offset so that physical page 1 is labelled `start-folio`.
  _folio-offset-state.update(start-folio - 1)
  _shaar-state.update(shaar)

  body

  // --- Notes metadata dump (for validator consumption) -------------------
  // Emits a single document-level metadata block, queryable via
  // `typst query build/book.typ '<notes-meta>' --field value --one`.
  context {
    let all-notes = query(footnote)
    let counters = (:)
    let data = ()
    for n in all-notes {
      let st = _stream-of(n)
      let ch = _chapter-of(n)
      let key = st + "-" + str(ch)
      let idx = counters.at(key, default: 0) + 1
      counters.insert(key, idx)
      let body-text = _note-body-text(n)
      let codepoints = body-text.clusters()
      let max = calc.min(25, codepoints.len())
      data.push((
        stream: st,
        chapter: ch,
        page: n.location().page(),
        index_in_stream: idx,
        marker: "[" + hebrew-numeral(idx) + "]",
        body_first_25chars: codepoints.slice(0, max).join(""),
      ))
    }
    [#metadata(data)<notes-meta>]
  }
}
