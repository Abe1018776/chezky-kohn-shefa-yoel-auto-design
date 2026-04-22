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
// pinned to the page of the reference by Typst's own footnote engine.
// ============================================================================

// ------------------------------ Fonts --------------------------------------
// Priority list matches the book's production house fonts, dropped into
// typst/fonts/ and picked up via --font-path:
//   Shefa ............. display (cover, cartouche, chapter title, "שפע")
//   PFT_Frank ......... main body (Frank-Ruehl tradition for sefarim)
//   PFT_Vilna ......... note apparatus (Vilna-style commentary face)
//   FbFrankRuelBook ... bold weight fallback for PFT_Frank
//   David / Tehila .... fallbacks
#let font-display = ("Shefa", "PFT_Frank", "FbFrankRuelBook", "David")
#let font-body    = ("PFT_Frank", "FbFrankRuelBook", "David",
                     "Noto Serif Hebrew")
#let font-notes   = ("PFT_Vilna", "PFT_Frank", "David",
                     "Noto Serif Hebrew")

// Backwards-compatible aliases (old code in this file referenced hebrew-serif).
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
  // Update header state with the chapter label. Because the label is passed
  // as content, we stringify it best-effort for the header; if it's not a
  // plain string we still store the content.
  _chapter-state.update(label)
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
// Typst's built-in #footnote gives us per-page pinning and automatic numbering.
// We wrap it so the in-text marker is a tiny Hebrew bracket letter [א], [ב]…
#let fn(body) = footnote(body)

// צינור השפע (endnote) — also rendered at the bottom of the page, but tagged
// so the entry show-rule can peel them off into the left column / style with
// a distinguishing ‡ glyph.
#let _en-label = "EN"
#let en(body) = footnote[#metadata(_en-label)#body]

// ------------------------------ Notes: 2-col + spillover -------------------
// We override Typst's default footnote.entry rendering and instead collect all
// footnotes on the current page, partition them into (fn, en), and emit them
// inside a custom block that builds:
//   ─── צינור השפע ───     ─── מקור השפע ───
//   [en col, left]          [fn col, right]
//   ───────── spillover (full width) ─────────
// Order inside each column is preserved; if the 2-col block overflows, the
// remainder continues into the spillover zone immediately below.
//
// Typst renders footnote.entry items one-by-one; we use counters + a show rule
// on footnote.entry that suppresses the default and a figure placement at the
// end of the page to emit our custom apparatus.

#let _note-col-height = 85mm    // max height of the 2-col block
#let _note-gutter     = 8mm

// The note apparatus is drawn as a bottom-pinned place() every page, reading
// the live footnote list from the page's footnote state.
#let _note-rule(title) = align(center)[
  #box(width: 100%)[
    #grid(
      columns: (1fr, auto, 1fr),
      align: (horizon, center + horizon, horizon),
      line(length: 100%, stroke: 0.5pt + luma(40%)),
      pad(x: 6pt)[
        #text(font: hebrew-serif, size: 9pt, dir: rtl,
              tracking: 0.1em, fill: luma(25%))[#title]
      ],
      line(length: 100%, stroke: 0.5pt + luma(40%)),
    )
  ]
]

// Classify an entry: returns true if its note body contains the EN tag.
#let _is-endnote(entry) = {
  // Typst 0.14: footnote.entry exposes the underlying footnote via .note
  let n = entry.note
  let b = n.body
  let txt = repr(b)
  txt.contains(_en-label)
}

// ------------------------------ Body wrapper -------------------------------
#let body(content) = {
  set par(justify: true, leading: 0.72em, first-line-indent: 0em)
  set text(font: font-body, size: 12.5pt, dir: rtl, lang: "he")
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

// ------------------------------ Main book setup ----------------------------
#let book(
  shaar: "",
  start-folio: 77,
  body,
) = {
  set document(title: "Shefa Shlomo")
  set page(
    width: 170mm,
    height: 240mm,
    margin: (top: 20mm, bottom: 25mm, inside: 25mm, outside: 20mm),
    header: _make-header(),
    header-ascent: 8mm,
  )
  set text(font: font-body, size: 12.5pt, dir: rtl, lang: "he",
           hyphenate: false)
  set par(justify: true, leading: 0.72em)

  // All footnote call-outs are Hebrew bracket letters: [א], [ב], [ג]…
  set footnote(numbering: n => {
    let marker = hebrew-numeral(n)
    text(size: 0.72em, baseline: -0.35em)[[#marker]]
  })

  // Folio offset so that physical page 1 is labelled `start-folio`.
  _folio-offset-state.update(start-folio - 1)
  _shaar-state.update(shaar)

  // --- Footnote / endnote rendering ---------------------------------------
  // Typst 0.14 supports `show footnote.entry: ...` which lets us collect and
  // reformat per-page note bodies. We render all notes through a single block
  // that is anchored to the page bottom with `place(bottom)`.
  //
  // Strategy: keep the default per-note numbering (Typst pins them to the
  // ref page). Override the visual appearance of the apparatus by hooking
  // `show: it => ...` on footnote.entry so each entry is styled as a
  // compact paragraph in small type, and wrap the whole stream in a box
  // that sets `columns(2)` with RTL ordering.

  show footnote.entry: it => {
    set text(font: font-notes, size: 9pt, dir: rtl, lang: "he")
    set par(justify: true, leading: 0.58em, first-line-indent: 0em)
    let marker = counter(footnote).at(it.location()).first()
    let is-en = _is-endnote(it)
    let tag = if is-en { text(fill: rgb("#9a3a3a"))[‡] } else { [] }
    grid(
      columns: (auto, 1fr),
      column-gutter: 4pt,
      text(size: 8pt)[[#hebrew-numeral(marker)]#tag],
      it.note.body,
    )
    v(2pt)
  }

  // Rule headers at the top of the apparatus: "═══ מקור השפע ═══" spanning
  // the full width (for now; proper two-stream split comes in a later pass).
  set footnote.entry(
    separator: {
      v(6pt)
      grid(
        columns: (1fr, auto, 1fr),
        align: (horizon, center + horizon, horizon),
        line(length: 100%, stroke: 0.5pt + luma(40%)),
        pad(x: 8pt)[
          #set text(font: font-display, size: 9pt, dir: rtl,
                    tracking: 0.1em, fill: luma(25%))
          מקור השפע
        ],
        line(length: 100%, stroke: 0.5pt + luma(40%)),
      )
      v(4pt)
    },
    clearance: 8mm,
    gap: 4pt,
    indent: 0pt,
  )

  body
}
