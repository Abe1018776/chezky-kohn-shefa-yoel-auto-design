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
// 1-based running index of the subtitle stream. Incremented in subtitle().
// Used by the <subtitle-loc> metadata tag so validators can locate and
// crop each subtitle strip via its actual render-position rather than a
// fixed-Y ROI (opener-page cartouche + chapter_title zones shift the
// subtitle's y-coordinate off the body-page default).
#let _subtitle-count-state = state("subtitle-count", 0)

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

// ------------------------------ Plain-text logical dump --------------------
// Each public API function below emits a `<plain-line>` metadata tag
// capturing the text that block contributes, in logical reading order. At
// build time, `typst query '<plain-line>' --field value` returns the list
// of all tags in document order; concatenated with newlines, this becomes
// `build/book.plain.txt` — the authoritative plain-text witness for what
// the PDF actually rendered (see VAL-M1-002 / VAL-CROSS-008).
//
// Because #fn / #en emit their own <plain-line> tags inline within body
// content, the emission order matches the reading order: body text first,
// then its footnote bodies, then its endnote bodies.

// Extract rendered plain text from an arbitrary content value. Mirrors
// _note-body-text further down but operates on raw content passed to the
// public template API (chapter label/title, subtitle, body). Skips
// `footnote` and `metadata` children so that inline #fn[...] / #en[...]
// call-outs do not duplicate their note bodies into the body line —
// those notes emit their own <plain-line> entries via fn/en below.
#let _content-text(node) = {
  if type(node) == str { return node }
  let walk(n) = {
    if type(n) == str { return n }
    let f = n.func()
    let fname = repr(f)
    // Skip elements whose bodies are already tracked separately (footnotes
    // emit their own <plain-line> via fn/en wrappers) or carry no reader-
    // visible text at all (raw metadata tags).
    if f == footnote or f == metadata { return "" }
    // Space, linebreak, parbreak, and smartquote are separate content
    // elements — not text leaves — so they won't surface via the "text"
    // field walk below. Match them by their repr name (they are not
    // exported as top-level identifiers in Typst 0.14) so the extracted
    // plain-line preserves word boundaries and quotation marks.
    if fname == "space" { return " " }
    if fname == "linebreak" { return " " }
    if fname == "parbreak" { return " " }
    if fname == "smartquote" {
      let fields = n.fields()
      if fields.at("double", default: true) { return "\"" } else { return "'" }
    }
    let fields = n.fields()
    if "text" in fields { return n.text }
    if "children" in fields {
      let s = ""
      for c in n.children { s = s + walk(c) }
      return s
    }
    if "body" in fields { return walk(n.body) }
    return ""
  }
  walk(node)
}

#let _emit-plain(line) = [#metadata(line)<plain-line>]

// ------------------------------ Chapter entry ------------------------------
// NOTE: No pagebreak here. Under the M2 round-4 pair-keep pagination model,
// python/convert.py is the pagination authority — it emits one
// `#page(margin: (bottom: Xmm))[...]` block per logical page, so the
// caller places chapter() directly at the top of each chapter-opener
// page. A `weak` pagebreak inside chapter() would interact badly with the
// #page(..)[body] wrapping (it could split the opener's subtitle+body
// onto a stray blank page).
#let chapter(label, title) = {
  _emit-plain("[CHAPTER] " + _content-text(label))
  _emit-plain("[CHAPTER_TITLE] " + _content-text(title))
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
// Emits a <plain-line> tag (used by build/book.plain.txt) AND a
// <subtitle-loc> metadata tag carrying the subtitle's rendered position
// (index_in_stream, page, x, y in pt). Validators MUST use this tag to
// sample the actual subtitle strip — see .factory/library/user-testing.md
// §"Subtitle sampling guidance". A fixed-Y ROI crop will land on the
// centred cartouche on opener pages (1, 7, 12) because the subtitle
// sits below the cartouche + chapter_title zones there.
//
// Defensive hardening: `#set par(justify: false)` inside the inner
// block ensures that even if the outer document-scope justify rule
// changes, or a subtitle ever wraps to 2+ lines, short single-line
// subtitles remain right-anchored (i.e. their right edge hugs the
// page right margin rather than drifting inward via justification).
#let subtitle(s) = {
  _emit-plain("[SUBTITLE] " + _content-text(s))
  _subtitle-count-state.update(c => c + 1)
  v(2mm)
  align(right)[
    #set text(font: font-body, size: 10.5pt, dir: rtl, lang: "he",
              fill: luma(45%), tracking: 0.08em)
    #set par(justify: false)
    #context {
      let pos = here().position()
      [#metadata((
        index_in_stream: _subtitle-count-state.get(),
        page: pos.page,
        x_pt: pos.x.pt(),
        y_pt: pos.y.pt(),
      ))<subtitle-loc>]
    }
    #s
  ]
  v(1mm)
}

// ------------------------------ Note call-outs -----------------------------
// Each public note-call wraps Typst's native #footnote so page-pinning is
// handled automatically. The body is prefixed with a
// metadata((stream, zone, chapter)) tuple that survives the layout pass
// (verified via Probe 3 in .factory/library/typst-notes.md).
//
// M2 partition: the Python converter (python/convert.py) pre-splits each
// block's fn / en stream into a column-fitting prefix and a spillover
// remainder, and emits one of SIX wrappers per note body:
//
//   #fn-col[body]        → right column of the 2-col apparatus (מקור השפע)
//   #en-col[body]        → left  column of the 2-col apparatus (צינור השפע)
//   #fn-spill[body]      → full-width spillover row, fn overflow portion
//   #en-spill[body]      → full-width spillover row, en overflow portion
//   #fn-spill-cont[body] → marker-less tail of a split first fn note
//   #en-spill-cont[body] → marker-less tail of a split first en note
//
// Each wrapper accepts a `src` named parameter carrying the source
// JSON block index the note originated from. This is tagged in the
// footnote metadata so VAL-M2-012 (block pair-keep invariant) can be
// checked programmatically: every note's rendered page must equal its
// source block's rendered page (save the body-exceeds-page escape).
//
// The `zone` tag ("col" / "spill" / "spill-cont") is read by
// `_apparatus()` below to partition per-page notes into the 2-col grid
// and the spillover row. The `stream` tag ("fn" or "en") is used for
// per-stream per-chapter marker numbering (VAL-M1-005 / M1-006 /
// M1-008) — markers are indexed by (stream, chapter) regardless of
// zone, so a note that overflows into the spillover still gets the
// next letter in its stream.
//
// Chapter number comes from _chapter-num-state and is resolved at call
// time via a context wrapper. A <plain-line> tag is also emitted at the
// call site (i.e. in the body paragraph), carrying the note's plain
// text so the Typst-side logical-order dump stays in sync with rendered
// content.
#let fn-col(body, src: 0) = {
  _emit-plain("[FN] " + _content-text(body))
  context {
    footnote([#metadata(("fn", "col", _chapter-num-state.get(), src)) #body])
  }
}
#let en-col(body, src: 0) = {
  _emit-plain("[EN] " + _content-text(body))
  context {
    footnote([#metadata(("en", "col", _chapter-num-state.get(), src)) #body])
  }
}
#let fn-spill(body, src: 0) = {
  _emit-plain("[FN] " + _content-text(body))
  context {
    footnote([#metadata(("fn", "spill", _chapter-num-state.get(), src)) #body])
  }
}
#let en-spill(body, src: 0) = {
  _emit-plain("[EN] " + _content-text(body))
  context {
    footnote([#metadata(("en", "spill", _chapter-num-state.get(), src)) #body])
  }
}

// Spillover continuation wrappers: used when the Python converter has
// SPLIT a single over-long note so its head goes in the column and its
// tail flows into the spillover. The tail keeps the same stream tag
// but uses zone tag "spill-cont" so the apparatus knows to render it
// WITHOUT a marker (the head already carries the note's sole marker).
// The counter helpers (_compute-labels, show-footnote) also treat
// "spill-cont" as a non-incrementing entry so markers stay contiguous.
#let fn-spill-cont(body, src: 0) = {
  _emit-plain("[FN] " + _content-text(body))
  context {
    footnote([#metadata(("fn", "spill-cont", _chapter-num-state.get(), src)) #body])
  }
}
#let en-spill-cont(body, src: 0) = {
  _emit-plain("[EN] " + _content-text(body))
  context {
    footnote([#metadata(("en", "spill-cont", _chapter-num-state.get(), src)) #body])
  }
}

// Back-compat shims: legacy M1 callers (probes, bare-template examples)
// that emit #fn / #en still work, mapping to the column zone by default.
// The generated book.typ from convert.py uses only the six new wrappers.
#let fn(body, src: 0) = fn-col(body, src: src)
#let en(body, src: 0) = en-col(body, src: src)

// ------------------------------ Body wrapper -------------------------------
// `src` names the source-JSON block index, used by VAL-M2-012 to match
// each note to the body block it originated from. The body emits a
// <body-loc> metadata tag (src + rendered page) so validators can
// reconstruct "this body was on page P" per source block index.
#let body(content, src: 0) = {
  // Emit the body-line BEFORE rendering so it appears before any nested
  // [FN]/[EN] plain-lines (which are emitted inline within content).
  _emit-plain("[BODY] " + _content-text(content))
  set par(justify: true, leading: 1.15em, first-line-indent: 0em)
  set text(font: font-body, size: 16pt, dir: rtl, lang: "he")
  context {
    [#metadata((src: src, page: here().page()))<body-loc>]
  }
  content
}

// ------------------------------ Ornament (chapter end) ---------------------
#let ornament() = {
  _emit-plain("[ORNAMENT]")
  v(1fr)
  align(center)[
    #text(size: 22pt, fill: luma(30%))[#sym.dash.em#h(2pt)#sym.infinity#h(2pt)#sym.dash.em]
  ]
  v(1fr)
}

// ------------------------------ Notes apparatus helpers --------------------
// Extract (stream, zone, chapter, src) tuple from a queried footnote
// element. The body is a sequence whose first child is
// `metadata((stream, zone, chapter, src))`.
//
// Backwards-compatible: if the metadata is a 3-tuple (legacy M2 round-1),
// return (stream, zone, chapter, 0). If it's a 2-tuple (legacy M1),
// return (stream, "col", chapter, 0).
#let _note-meta(n) = {
  let c = n.body.children
  if c.len() > 0 and c.first().func() == metadata and type(c.first().value) == array {
    let v = c.first().value
    if v.len() >= 4 {
      (v.at(0), v.at(1), v.at(2), v.at(3))
    } else if v.len() == 3 {
      (v.at(0), v.at(1), v.at(2), 0)
    } else if v.len() == 2 {
      (v.at(0), "col", v.at(1), 0)
    } else {
      ("fn", "col", 0, 0)
    }
  } else {
    ("fn", "col", 0, 0)
  }
}
#let _stream-of(n)  = _note-meta(n).at(0)
#let _zone-of(n)    = _note-meta(n).at(1)
#let _chapter-of(n) = _note-meta(n).at(2)
#let _src-of(n)     = _note-meta(n).at(3)

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

// Extract the renderable content (metadata + leading space stripped) from
// a footnote node. Used by the apparatus to lay out the note body inside
// the appropriate visual region (column or spillover row).
#let _note-render-content(n) = n.body.children.slice(2).join()

// Given a note and a parallel list of all notes in document order,
// compute its 1-based index within its (stream, chapter) cohort. The
// ``col`` / ``spill`` zones both increment the per-stream counter, so
// a note that overflows into the spillover zone still gets the next
// letter in its stream. The ``spill-cont`` zone — used for the tail
// of a SPLIT first note — is treated as a non-marker continuation: it
// inherits the marker of its preceding ``col`` head (same (stream,
// chapter) cohort) and does NOT advance the counter.
//
// labels.at(i) is 0 for continuation entries (sentinel — validators
// and renderers check the zone tag and skip marker emission when
// zone == "spill-cont").
#let _compute-labels(all-notes) = {
  let counters = (:)
  let labels = ()
  for n in all-notes {
    let st = _stream-of(n)
    let zn = _zone-of(n)
    let ch = _chapter-of(n)
    let key = st + "-" + str(ch)
    if zn == "spill-cont" {
      // Continuation entry — inherit counter value of the previous
      // head (do NOT increment). Label 0 sentinel flags "no marker".
      labels.push(0)
    } else {
      let cur = counters.at(key, default: 0) + 1
      counters.insert(key, cur)
      labels.push(cur)
    }
  }
  labels
}

// Render one note: [מָרְכֵּר] note body text (wrapped as a compact grid
// row). When ``marker == 0`` (continuation sentinel from _compute-
// labels), the [letter] cell is replaced by an empty 0pt column so the
// body aligns flush-left, matching the reference scans' split-note
// continuation pattern.
#let _render-note(marker, note-body) = {
  if marker == 0 {
    // Continuation — no in-apparatus marker. Flow the body directly.
    note-body
    v(2pt)
  } else {
    grid(
      columns: (auto, 1fr),
      column-gutter: 4pt,
      text(size: 8pt)[[#hebrew-numeral(marker)]],
      note-body,
    )
    v(2pt)
  }
}

// Render the stream of notes for a single column. Commentary type —
// PFT_Vilna 9pt — matches the reference scans' apparatus typography and
// is deliberately identical to the spillover row below it (VAL-M2-007
// typography parity).
#let _render-stream(notes, labels, all-notes-loc) = {
  set text(font: font-notes, size: 9pt, dir: rtl, lang: "he")
  set par(justify: true, leading: 0.58em, first-line-indent: 0em,
          spacing: 0.25em)
  for n in notes {
    let i = all-notes-loc.position(loc => loc == n.location())
    let marker = labels.at(i)
    _render-note(marker, _note-render-content(n))
  }
}

// Render the full-width spillover row. Typography matches _render-stream
// above (PFT_Vilna 9pt, same leading / justification) so the transition
// from the 2-col grid into the spillover is seamless — no visible type
// jump (VAL-M2-007).
//
// Called with the fn-spill(+cont) notes FIRST, then the en-spill(+cont)
// notes. When both are non-empty, fn overflow precedes en overflow in
// the rendered stream (VAL-M2-003). Regular spill entries get the next
// [letter] marker in their (stream, chapter) cohort; continuation
// entries (``spill-cont``, marker == 0) render marker-less, flowing as
// a natural continuation of their head in the column above.
#let _render-spillover(fn-spill, en-spill, labels, all-notes-loc) = {
  // PFT_Vilna 9pt — commentary font at the same size as the 2-col grid.
  set text(font: font-notes, size: 9pt, dir: rtl, lang: "he")
  set par(justify: true, leading: 0.58em, first-line-indent: 0em,
          spacing: 0.25em)
  for n in fn-spill {
    let i = all-notes-loc.position(loc => loc == n.location())
    let marker = labels.at(i)
    _render-note(marker, _note-render-content(n))
  }
  for n in en-spill {
    let i = all-notes-loc.position(loc => loc == n.location())
    let marker = labels.at(i)
    _render-note(marker, _note-render-content(n))
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
// partitions by (stream, zone), and emits:
//
//   1. the 2-column grid for notes tagged zone == "col"
//      (right = מקור השפע / fn, left = צינור השפע / en), with the
//      appropriate rule-header(s) depending on which streams appear;
//   2. directly below, a full-width spillover row for notes tagged
//      zone == "spill", rendered in the same commentary type (PFT_Vilna
//      9pt) so the transition is typographically seamless
//      (VAL-M2-002 / M2-007). fn-spill notes precede en-spill notes,
//      preserving stream order (VAL-M2-003).
//
// Spillover is ONLY rendered alongside at least one column note
// (VAL-M2-008). On pages with no notes at all, a thin decorative rule
// keeps the notes-zone band visually consistent with the rest of the
// book (and makes the audit's dark-row heuristic trigger predictably).
//
// Body-text position does NOT shift on spillover pages: the apparatus
// renders into the pre-reserved 75mm bottom margin (see `set page(
// margin: (bottom: 75mm))` in `book`), and spillover fills the lower
// half of that band without pushing the body frame upward
// (VAL-M2-010).
#let _apparatus() = context {
  let pg = here().page()
  let all-notes = query(footnote)
  let labels = _compute-labels(all-notes)
  let all-locs = all-notes.map(n => n.location())
  let notes-here = all-notes.filter(n => n.location().page() == pg)

  // Partition by (stream, zone). ``spill`` and ``spill-cont`` both
  // belong to the spillover zone — continuations are markerless tails
  // of a col-head note but render in the same full-width band.
  let _is-spill(n) = _zone-of(n) == "spill" or _zone-of(n) == "spill-cont"
  let fn-col-notes   = notes-here.filter(n => _stream-of(n) == "fn" and _zone-of(n) == "col")
  let en-col-notes   = notes-here.filter(n => _stream-of(n) == "en" and _zone-of(n) == "col")
  let fn-spill-notes = notes-here.filter(n => _stream-of(n) == "fn" and _is-spill(n))
  let en-spill-notes = notes-here.filter(n => _stream-of(n) == "en" and _is-spill(n))

  let has-col-notes = fn-col-notes.len() + en-col-notes.len() > 0
  let has-spillover = fn-spill-notes.len() + en-spill-notes.len() > 0

  v(0.4em)
  if notes-here.len() == 0 {
    // No notes on this page — emit a thin decorative rule so the page's
    // notes-zone band remains visually continuous with the rest of the
    // book (and the audit's dark-row heuristic triggers consistently).
    align(center)[
      #line(length: 30%, stroke: 0.6pt + luma(35%))
    ]
  } else if not has-col-notes {
    // Only spillover? VAL-M2-008 requires spillover to appear ONLY
    // alongside at least one column note. Defensive branch: if the
    // partitioner somehow produces spill-only, fall back to rendering
    // those notes in a single centered-header zone so nothing is lost.
    _rule-header([מקור השפע])
    v(0.3em)
    block(width: 100%)[#_render-spillover(fn-spill-notes, en-spill-notes, labels, all-locs)]
  } else if en-col-notes.len() == 0 and en-spill-notes.len() == 0 {
    // Case A: footnotes only — single centered header, no left column.
    _rule-header([מקור השפע])
    v(0.3em)
    block(width: 100%)[#_render-stream(fn-col-notes, labels, all-locs)]
    if has-spillover {
      v(0.4em)
      block(width: 100%)[#_render-spillover(fn-spill-notes, en-spill-notes, labels, all-locs)]
    }
  } else if fn-col-notes.len() == 0 and fn-spill-notes.len() == 0 {
    // Rare: endnotes only — single centered header, no right column.
    _rule-header([צינור השפע])
    v(0.3em)
    block(width: 100%)[#_render-stream(en-col-notes, labels, all-locs)]
    if has-spillover {
      v(0.4em)
      block(width: 100%)[#_render-spillover(fn-spill-notes, en-spill-notes, labels, all-locs)]
    }
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
      block(width: 100%)[#_render-stream(fn-col-notes, labels, all-locs)],
      [],
      block(width: 100%)[#_render-stream(en-col-notes, labels, all-locs)],
    )
    if has-spillover {
      v(0.4em)
      block(width: 100%)[#_render-spillover(fn-spill-notes, en-spill-notes, labels, all-locs)]
    }
  }
}

// ------------------------------ Main book setup ----------------------------
#let book(
  shaar: "",
  start-folio: 77,
  body,
) = {
  set document(title: "Shefa Shlomo")
  // M2 round-4 PAIR-KEEP PAGINATION: convert.py is the pagination
  // authority. It emits per-page `#page(margin: (bottom: Xmm))[...]`
  // blocks, where X is sized to the cumulative notes-zone height for
  // that page's committed blocks. The default bottom margin below is
  // only a fallback for any ambient content (e.g. the trailing
  // metadata-dump `context {}` block) — every content-bearing page in
  // a pair-keep build has an explicit per-page override. The previous
  // "fixed 75mm on every page" value from M2 round-1 (commit 969eebb)
  // was reverted because it wasted real estate on light-notes pages
  // and forced more total pages than necessary. Body TOP-y stays at
  // top-margin; body BOTTOM-y varies per page by design.
  set page(
    width: 170mm,
    height: 240mm,
    margin: (top: 22mm, bottom: 25mm, inside: 25mm, outside: 20mm),
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
  // Computed lazily via query(selector).before(here()). The zone tag
  // distinguishes markerless continuation entries (``spill-cont``)
  // from regular notes: continuations emit NO in-text marker and don't
  // advance the per-(stream, chapter) counter. Regular notes (``col``
  // or ``spill``) each contribute +1 to the counter — so a note that
  // overflows into the spillover still gets the next letter in its
  // stream (VAL-M1-005 / M1-008).
  show footnote: it => context {
    let meta = _note-meta(it)
    let st = meta.at(0)
    let zn = meta.at(1)
    let ch = meta.at(2)
    if zn == "spill-cont" {
      // Continuation — no marker in body text (the head's marker is
      // the note's sole in-text call-out).
      return []
    }
    let priors = query(selector(footnote).before(here())).filter(n => {
      let m = _note-meta(n)
      m.at(0) == st and m.at(2) == ch and m.at(1) != "spill-cont"
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
      let zn = _zone-of(n)
      let ch = _chapter-of(n)
      let key = st + "-" + str(ch)
      // Continuations share the preceding head's index — read it back
      // from counters without incrementing.
      let is-cont = zn == "spill-cont"
      let idx = if is-cont {
        counters.at(key, default: 0)
      } else {
        counters.at(key, default: 0) + 1
      }
      if not is-cont {
        counters.insert(key, idx)
      }
      let body-text = _note-body-text(n)
      let codepoints = body-text.clusters()
      let max = calc.min(25, codepoints.len())
      data.push((
        stream: st,
        zone: zn,
        chapter: ch,
        page: n.location().page(),
        source_block_index: _src-of(n),
        index_in_stream: idx,
        marker: if is-cont { "" } else { "[" + hebrew-numeral(idx) + "]" },
        body_first_25chars: codepoints.slice(0, max).join(""),
      ))
    }
    [#metadata(data)<notes-meta>]
  }
}
