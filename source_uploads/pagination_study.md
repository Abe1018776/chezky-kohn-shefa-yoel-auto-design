# Reverse-Engineering the Pagination of a Hasidic Sefer

### From `docx_content_with_notes.json` → PDF pages 105–124

A research study of 20 algorithms and libraries — from "easy to wire up in an afternoon" to "industrial typesetting pipeline" — plus a meticulous specification of the layout rules actually used by the source PDF.

---

## Part I — What the input is, what the output is, and the rules in between

### 1.1 Input: the JSON

The file `docx_content_with_notes.json` has this shape:

```
{
  "pdf_page_range_images": { "from_page": 105, "to_page": 124 },
  "docx_content": [ 51 blocks, index 1..51 ]
}
```

Each `docx_content` block is one of four kinds of things, distinguished by length and content only (there is no explicit `type` field — inferring the type is the first job of any renderer):

| Kind | How to detect | Example |
|---|---|---|
| **Chapter opener** (`<h1>`) | `text` starts with `"פרק "` and is ≤ 6 chars | `"פרק א"`, `"פרק ב"`, `"פרק ג"` |
| **Chapter title / motto** (`<h2>`) | Short (≤ 40 chars), vowelised (contains niqqud), directly follows a chapter opener | `"הַשִּׁיר וְהַשֶּׁבַח לְחַי עוֹלָמִים"` |
| **Section subtitle** (`<h3>`) | Short (≤ ~80 chars), **no** leading `א. / ב. / ג.`, no niqqud | `"הנסים והנפלאות נמשכים לדורות - לפיכך יש להודות עליהם לעולם"` |
| **Section body** (`<p>`) | Long, starts with a Hebrew letter + `"."` (`א.`, `ב.`, `ג.`…) | `"א. מצוה עלינו להודות ולשבח…"` |
| **End-of-chapter mark** | `text == "*"` | `"*"` — renders as the winged-ornament glyph |

Each body block carries two note arrays:

* `footnotes[]` — every item has `{id, text}`, and inside the body text is an inline reference like `[א]`, `[ב]`… These are the **מקור השפע** (source) notes.
* `endnotes[]` — same shape, rendered as **צינור השפע** (conduit) notes, numbered independently (`[א]`, `[ב]`… reset per block of endnotes).

The body text also contains inline tokens like `א]` that are the call-outs for footnote `id="1"`, `ב]` for `id="2"`, etc. The bracket letter is the Hebrew alphabet counter — not the footnote's absolute `id`. A renderer has to map `footnote_refs[i] → footnotes[i]` positionally, not by the literal number in the bracket.

**Sizes (measured on your exact file):**

| Measure | Value |
|---|---|
| Main-body paragraphs | 21 (mean 333 chars, max 549) |
| Footnotes | 24 (mean 877 chars, max 1,687) |
| Endnotes | 10 (mean 1,450 chars, max 5,146) |
| Total characters | ~42,500 |
| Pages used | 17 (pages 105–122 minus the blank 123 and cover 124) |
| Characters per printed page | **≈ 2,500** |
| Notes-to-body ratio | **5× more note text than body text** |

That 5× ratio is the single most important number in the whole study: it's why this sefer looks the way it does.

---

### 1.2 Output: the page anatomy

Every content page (105–122) is drawn from **eight discrete zones**, in this RTL, top-to-bottom reading order:

```
┌──────────────────────────────────────────────────────────────┐
│  [folio #]   שלמה   ‹שפע›   [chapter/שער name]    (blank)    │  ← Running header
├──────────────────────────────────────────────────────────────┤
│                                                              │
│                    ┌─────────────────┐                       │
│                    │     פרק א       │   ← cartouche          │  ← Chapter opener
│                    └─────────────────┘       (only on p.105,  │     (conditional)
│             הַשִּׁיר וְהַשֶּׁבַח לְחַי עוֹלָמִים       114, 119)          │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│         [section subtitle in small grey caps]                │  ← Subtitle
│                                                              │
│  א.  [main body text, large, justified, RTL, drop-letter    │  ← Main body
│       for the letter marker; footnote refs as ᵃ ᵇ in         │     (1..n paragraphs
│       superscript small brackets]                            │      per page)
│                                                              │
├──────────────────────────────────────────────────────────────┤
│   ═══ צינור השפע ═══       ═══ מקור השפע ═══                │  ← Note rules
│                                                              │
│   [endnote column,         [footnote column,                 │  ← Notes (2-col)
│    narrower, smaller text,  narrower, smaller text,          │
│    left of the spine]       right of the spine]              │
│                                                              │
├──────────────────────────────────────────────────────────────┤
│   [overflow notes in full page width, smaller size]          │  ← Spillover zone
├──────────────────────────────────────────────────────────────┤
│                (decorative flourish, only on                 │  ← End-of-chapter
│                 pages 113, 118, 122)                         │     ornament
└──────────────────────────────────────────────────────────────┘
```

Not every zone is present on every page. The rules for which zones appear are:

1. **Running header** — always present on text pages. Contents read RTL: folio letter (e.g. `צ`), word `שלמה`, bold word `שפע` (centered, larger), then on chapter-opener pages the chapter label `פרק א`, and on interior pages the *shaar* (book-section) name `שער ההודאה`.
2. **Folio numbering** — Hebrew gematria letters, one increment per page (`עז=77 → פ=80 → צד=94`). Chapter openers and interior pages all share the same sequence — chapter breaks do **not** reset the folio.
3. **Chapter cartouche** — an oval frame with `פרק X` inside, then a vowelised title below, appears only on the first page of a chapter and pushes the body text roughly 40% down the page.
4. **Section subtitle** — rendered in a smaller, grey, letter-spaced face, about 0.6em above the paragraph it introduces.
5. **Main body** — the dominant visual weight. First letter marker (`א.`, `ב.`…) is rendered as a display glyph (bold, ~1.4× the body size). Footnote call-outs appear inline as tiny bracketed Hebrew letters in superscript.
6. **Notes block**, the crucial piece. See §1.3 below.
7. **Spillover zone** — see §1.3.
8. **End-of-chapter ornament** — a small winged-cherub-like decorative glyph, horizontally centered, appears on the last page of each chapter (pages 113, 118, 122 in your sample).

---

### 1.3 The notes block — the hardest part of the layout

This is where 90% of the engineering difficulty lives. I observed four distinct cases across pages 105–122:

**Case A — footnotes only (no endnotes for the sections on this page).**
Example: page 109. The footnote text spans **both columns of the two-column block**, right column first, then left column. The column rule header in the middle reads only `═══ מקור השפע ═══` — no left header. Implementations get this right only if they treat "number of column headers" as data-driven.

**Case B — footnotes and endnotes, both fit in the two-column block.**
Example: page 113. Right column is titled `═══ מקור השפע ═══`, left column is titled `═══ צינור השפע ═══`. The two columns are **independently typeset** — they do not share a flow. The footnotes fill the right column only; the endnotes fill the left only. They stop at whatever height they each need.

**Case C — footnotes and endnotes, but one overflows.**
Examples: pages 105, 108, 111, 116, 117. The two-column block has a **fixed maximum height** (roughly 40% of the page). Content that doesn't fit wraps down into a **single full-page-width zone** below the two columns. In the source PDF you can see that the footnote text in the overflow zone is the direct continuation of the right column — it's a "column-then-spill" pattern, not a balanced newspaper layout. The spillover paragraphs use the same smaller type as the columns above them.

**Case D — very long endnote (stories).**
Example: the endnote block on page 117 (1,700+ characters for the tale about the Rebbe of Radomsk). Endnotes can be 5× longer than footnotes, and when that happens the entire left column is devoted to one endnote, while the right column may finish multiple footnotes. Column heights are therefore **not equalized**.

The effective algorithm the typesetter used is:

```
1. Lay out main body for page → remember the y-offset where it ended.
2. Under the body, reserve a strip down to 85% of page height.
   Divide this strip into two columns separated by a gutter (~24pt).
3. Pour all footnotes for the sections visible on this page into the
   right column, top-down, until the column is full OR footnotes run out.
4. Pour all endnotes for the sections visible on this page into the
   left column, top-down, same stopping rule.
5. Any footnote/endnote text that did not fit spills into a single
   full-width paragraph zone below both columns, preserving order
   (footnotes first, then endnotes), using the same smaller type.
6. If the page is the last of a chapter, draw the ornament in the
   vertical middle of whatever whitespace remains.
```

That's the whole layout. Everything else (font choices, ornaments, header patterns) is decoration.

---

### 1.4 Page-break rules (the pagination policy)

Watching where breaks actually occurred:

* **No orphan lines.** A paragraph's first line is never left alone at the bottom of a page; a paragraph's last line is never left alone at the top.
* **Subtitle + first paragraph are kept together.** Pages 109, 115, 120 all start a new page with a subtitle; I never saw a subtitle orphaned at the bottom of a page.
* **Chapter openers force a new page.** When `text == "פרק ב"` is reached, the previous page ends (even if nearly empty), the winged ornament is drawn on it, and the cartouche starts fresh on the next page.
* **Notes always float with their reference.** When a footnote's in-text call-out (`[א]`) appears on page 116, the footnote body appears on page 116 — not on 117. This is a hard constraint and is why the note-block height is allowed to vary and why spillover exists.
* **Page height for main body is adaptive.** The main body zone shrinks on pages with heavy notes (sometimes 40% of the page is notes) and grows on pages with few or no notes (page 110 has only one paragraph of body and a full notes block; page 113 has one paragraph of body and only half a page of notes, then the ornament).

This is fundamentally a **"footnotes pin paragraphs to pages"** layout — the reverse of web-style "paginate main body, footnotes wrap later." Any algorithm that doesn't solve footnotes-pinned-to-references will produce wrong pages.

---

## Part II — Twenty approaches, ranked from easiest to most advanced

For each I give: **how it works**, **what it does well**, **where it breaks**, and **fitness** for this specific job (1–5 stars). Ratings assume the goal is "identical or near-identical output to the reference PDF for Hebrew RTL with floating footnotes and a 2-col overflow note block."

---

### Tier 1 — The weekend-project tier (HTML + CSS)

#### 1. Pure CSS Paged Media (`@page`, `size`, `running()`, `element()`) ★★☆☆☆

Write semantic HTML once, add a print stylesheet that uses `@page`, `@top-center`, `size: 170mm 240mm;` and `page-break-*`. Open in Chrome's Print-to-PDF.

* **Wins:** zero dependencies. Hebrew/RTL works because `dir="rtl"` + `lang="he"` is native. Authoring feels like writing an article.
* **Breaks:** Chrome doesn't implement `float: footnote`, `@footnote`, or the running-element spec. You cannot pin a note to its reference page — Chrome just puts all `position:footnote` content on the last page of the document. The two-column footnote block with spillover is unimplementable. Also: no running headers beyond fixed text.
* **Fitness:** fine for a reading-web preview, useless for PDF parity. ★★☆☆☆

#### 2. Paged.js ★★★☆☆ ([Paged.js](https://pagedjs.org))

A JavaScript polyfill that implements the **CSS Generated Content for Paged Media (GCPM)** spec on top of a real browser. You write `@page`, `running()`, `counter(page, hebrew)`, `string-set`, and — crucially — `float: footnote` + `::footnote-marker`, and Paged.js actually paginates them into real page boxes in the browser DOM, which you then print to PDF.

* **Wins:** declarative, debuggable in DevTools, open source. Supports Hebrew page counters (`counter-style`). Handles floating footnotes per page. Good RTL support via the underlying browser. Active community.
* **Breaks:** The two-column note block + spillover isn't a one-liner — you'd implement it as a custom Paged.js "chunker" plugin or by pre-partitioning the note text into "goes in right column / goes in left column / goes in spillover" before it hits the DOM. Hebrew letter drop-caps need custom CSS (`::first-letter` works). Performance is noticeable on 20+ page books (a few seconds).
* **Fitness:** **the sweet spot for this project** if you're comfortable in JS/CSS. You'll get 95% of the output with 20% of the effort vs. a full typesetting pipeline. ★★★★☆

#### 3. Vivliostyle (CLI + viewer) ★★★☆☆ ([Vivliostyle](https://vivliostyle.org))

Conceptually the same as Paged.js (GCPM-in-browser) but with a heavier toolchain: Markdown/HTML/CSS → Chromium headless → PDF, plus a live-preview "Viewer." Produced by people publishing real books.

* **Wins:** Better RTL than Paged.js in practice (bi-di edge cases handled). Native CLI (`vivliostyle build`). Has first-class Hebrew examples in the gallery.
* **Breaks:** Same footnote-spillover caveat as Paged.js. Ecosystem smaller than Paged.js's.
* **Fitness:** tied with Paged.js; pick whichever developer experience you like. ★★★★☆

#### 4. Pandoc with `--pdf-engine=xelatex` + Memoir/Koma-Script + `culmus` fonts ★★★☆☆

Convert JSON → pandoc-Markdown → PDF. Memoir class gives you headers, footnotes, and `\sidenote`. RTL via `polyglossia` + `\setmainlanguage{hebrew}` + XeLaTeX engine.

* **Wins:** closer to a "real" typesetting pipeline than CSS; footnotes are solved by LaTeX automatically.
* **Breaks:** the **two-column footnote block labeled מקור השפע / צינור השפע with spillover** is not in stock LaTeX. You'd combine `footmisc` (one-line footnotes), `perpage` (reset numbering), and `minipage`-based manual splitting — which is essentially rebuilding the problem. Also, Hebrew drop-caps and cartouches require hand-drawn TikZ.
* **Fitness:** works, but you end up writing LaTeX instead of CSS. ★★★☆☆

---

### Tier 2 — The library-assisted tier (programmatic layout)

#### 5. ReportLab (Python) with `Platypus` + custom `PageTemplate` ★★★☆☆ ([ReportLab docs](https://www.reportlab.com/dev/docs/))

The classic Python PDF library. You define `Frame` objects (rectangles on the page) and a `PageTemplate` per page-type ("chapter-opener", "body", "body-chapter-end"), then a `BaseDocTemplate` routes `Flowables` (paragraphs, images) through frames in order. Frames chain — when one fills, overflow goes to the next.

* **Wins:** exactly the right abstraction for your layout. Body frame → footnote-right frame → footnote-left frame → spillover frame is literally four `Frame` objects on a `PageTemplate`. Footnote-pinning is done by reserving variable-height frames and measuring flowables before page layout.
* **Breaks:** Hebrew/bidi support is weak out of the box — you'll need `python-bidi` + `arabic-reshaper`-style handling (there is a Hebrew fork), or pre-shape with HarfBuzz. No built-in hyphenation for Hebrew.
* **Fitness:** second-best in this list for a production pipeline, once the bidi hurdle is cleared. ★★★★☆

#### 6. WeasyPrint (Python) ★★★☆☆ ([WeasyPrint](https://weasyprint.org))

HTML + CSS → PDF, implemented from scratch in Python (not browser-based). Supports a decent subset of GCPM.

* **Wins:** one command (`weasyprint in.html out.pdf`), clean RTL, deterministic output (no Chromium).
* **Breaks:** footnote support is partial — `float: footnote` and `::footnote-call` work for simple cases but **not for a two-column footnote block with spillover**. You'd fall back to pre-computing the note placement in Python before emitting HTML.
* **Fitness:** great for simpler sefarim, borderline for this one. ★★★☆☆

#### 7. Prince XML ★★★★☆ ([Prince](https://www.princexml.com))

Commercial (free for non-commercial), the *reference* implementation of CSS paged media. Everything Paged.js *tries* to do, Prince does for real, plus more.

* **Wins:** the footnote primitives (`float: footnote`, `@footnote { column-count: 2 }`) actually work. Hebrew, page counters, running headers, cross-references — all declarative. Can produce `@page:first` (for cover), custom page types, and the output is high quality.
* **Breaks:** license cost for commercial use; the two-column-footnote + spillover combination is still niche and you may need Prince-specific CSS extensions or a small preprocessing step.
* **Fitness:** if budget allows, the fastest way to a polished result. ★★★★☆

#### 8. Typst ★★★★☆ ([Typst](https://typst.app))

A modern (2022+) typesetting language, written in Rust, with a Turing-complete markup/DSL and **near-TeX output quality**. Footnotes, page headers, multi-column layout, and custom functions for "reserve a 2-column block that spills into 1 column" are all a few lines of Typst code.

* **Wins:** the language was designed *for* documents like yours. Footnote pinning is built in. RTL is supported (`set text(dir: rtl)`), and Hebrew shaping via HarfBuzz is native. Far faster than LaTeX (compiles in milliseconds). The spillover pattern is expressible as a custom "place" function with a fallback.
* **Breaks:** ecosystem is young — a Hebrew-specific package (vowelisation, Taamim shaping edge cases) may need writing. No drop-in equivalent of some Memoir page-layout goodies yet.
* **Fitness:** **my top pick** for a from-scratch re-implementation that's maintainable and fast. ★★★★★

---

### Tier 3 — The heavy-guns typesetting tier

#### 9. XeLaTeX + Memoir + `bidi` + `polyglossia` + `fnpct` + `manyfoot` ★★★★☆

The "batteries-included" TeX stack for Hebrew sefarim. The interesting packages:

* `bidi` handles right-to-left setup.
* `polyglossia` is the multilingual replacement for `babel`.
* `manyfoot` provides **multiple independent footnote apparatuses per page** — one for מקור השפע, one for צינור השפע. This is exactly what the layout demands.
* `ftnright` or `dblfnote` puts footnotes in two columns.

* **Wins:** after you write the preamble once, every new sefer drops in. Traditional Jewish-book typography (Rashi-style commentary) is a solved problem in TeX.
* **Breaks:** preamble is hundreds of lines; fragile to package-version drift. The cartouche + winged ornament need TikZ. Spillover from two columns to one for a footnote block is still custom.
* **Fitness:** if you plan to publish many sefarim, the TeX investment amortizes. ★★★★☆

#### 10. LuaLaTeX + `bidi` + LuaTeX `attribute`-based page builder ★★★★☆

Same as #9, but LuaTeX lets you write Lua callbacks that intercept the page builder (`pre_linebreak_filter`, `vpack_filter`). You can literally script the "two-column notes, overflow to one" behavior in Lua.

* **Wins:** ultimate control. Lua scripts are reusable across sefarim.
* **Breaks:** steep; you're now a typesetting compiler author. Debugging is painful.
* **Fitness:** for a publisher shipping 20+ titles. ★★★☆☆

#### 11. ConTeXt (Mark IV) ★★★★☆ ([ConTeXt](https://wiki.contextgarden.net))

TeX's more modern cousin, designed around structured documents. Hebrew + footnote streams + cartouches are all first-class `\setup...` commands. Hans Hagen (its author) maintains it specifically for publishing workflows.

* **Wins:** cleaner than LaTeX for complex page layouts. Built-in support for multiple footnote series (`\definenote`). RTL maturely handled.
* **Breaks:** smaller community, fewer Stack Overflow answers, the syntax takes getting used to.
* **Fitness:** excellent but niche. ★★★★☆

#### 12. Adobe InDesign + IDML scripting ★★★★★

The professional-publishing answer. InDesign supports two-column footnote frames, threaded text frames, span/split columns, RTL stories, and first-line drop-caps out of the box. You script the layout with the IDML XML format (or JSX).

* **Wins:** pixel-perfect control; most commercial sefarim are typeset here. RTL and Hebrew OpenType features (precise vowel placement, kerning) are industry-leading.
* **Breaks:** not reproducible from code alone (InDesign is a GUI tool). IDML scripting is ugly. Licensing.
* **Fitness:** the **fidelity ceiling** — if you hand-layout one book, it will look better than any code can, but it doesn't scale. ★★★★★ for quality, ★★☆☆☆ for automation.

#### 13. QuarkXPress + XTension SDK ★★★☆☆

Historically the dominant RTL-heavy publishing tool for Hebrew and Arabic books. Similar trade-offs to InDesign; less common in 2026.

* **Fitness:** only if you inherit an existing Quark workflow. ★★★☆☆

---

### Tier 4 — The "roll your own" tier (low-level PDF generation)

#### 14. HarfBuzz + FreeType + libpdfium (or cairo) ★★★☆☆

Do the text shaping yourself. HarfBuzz turns a Unicode Hebrew string + niqqud into an array of `(glyph_id, x_advance, y_advance)` tuples. FreeType rasterizes or gives you outlines. Cairo or pdfium emits a PDF page.

* **Wins:** every layout decision is under your control — you decide exactly how niqqud stack on consonants. Same code can target PDF, SVG, and on-screen.
* **Breaks:** you are writing a typesetting engine. Line-breaking, justification, hyphenation, paragraph layout — **you write all of it**. Months of work.
* **Fitness:** only if existing engines have a bug you can't live with. ★★★☆☆

#### 15. PDFKit (Node) or pdf-lib (Node/browser) with custom layout ★★☆☆☆

Same story as ReportLab but in JavaScript. PDFKit has RTL support and decent font embedding; `pdf-lib` lets you draw into an existing PDF byte-accurately.

* **Wins:** lives in the same runtime as your JSON pipeline.
* **Breaks:** no higher-level "flowable with overflow into another frame" abstraction — you write it yourself.
* **Fitness:** good for small, highly custom one-off layouts; poor for books. ★★☆☆☆

#### 16. Custom SVG-per-page pipeline → cairosvg → PDF ★★★☆☆

Produce one SVG per page with absolute text positions, then stitch. Shaping with HarfBuzz (Python `uharfbuzz`), layout logic in pure Python.

* **Wins:** SVG is easy to debug (open one page in a browser). Hebrew niqqud render exactly as measured. Deterministic.
* **Breaks:** you're reimplementing line-breaking again. PDF output via cairo loses font hinting at small sizes.
* **Fitness:** good for proof-of-concept; not production. ★★★☆☆

---

### Tier 5 — The machine-learning & hybrid tier

#### 17. LLM-assisted layout planner + deterministic renderer (hybrid) ★★★★☆

Use an LLM (Claude/GPT) in a **planning role only**: give it the JSON + a page budget + a height formula, ask it to emit a per-page JSON plan (which paragraphs go on which page, which notes go where, whether spillover is needed). A small deterministic renderer (ReportLab, Typst, or Paged.js) consumes the plan and draws pixels. The LLM never touches glyphs — it only partitions text.

* **Wins:** the "which paragraphs fit on page N with these notes" decision is the hardest part of a traditional pipeline (it's a fitting problem that depends on measuring rendered text). An LLM is surprisingly good at approximating it from character counts you give it, and you validate the plan by re-measuring after rendering.
* **Breaks:** requires a feedback loop (render → measure → if overflow, replan). You'll iterate 2–3 times per book. Cost per book is a few cents in API calls.
* **Fitness:** **underrated for this exact problem**, because the layout is declarative but hard to express in rules. ★★★★☆

#### 18. OCR + reinforcement learning to match a reference PDF ★★☆☆☆

Tesseract or Google Vision OCRs the reference pages to get ground-truth paragraph boundaries. A layout policy (neural or rule-based) proposes renderings; a reward is computed as pixel/text similarity to the reference. Train until convergence.

* **Wins:** reproduces *this specific book* very well.
* **Breaks:** enormous complexity for a single book. Doesn't generalize without more data.
* **Fitness:** academic curiosity. ★★☆☆☆

#### 19. Diffusion or VLM-based direct rendering (e.g., TextDiffuser-2, image-generation models conditioned on text) ★★☆☆☆

Give a multimodal model the reference pages and ask it to "redraw" the input JSON as similar-looking pages.

* **Wins:** fast prototype.
* **Breaks:** Hebrew rendering from diffusion models in 2026 is still unreliable (niqqud hallucinate, ligatures invert). Output is an image, not selectable/searchable PDF text. Completely unfit for a published sefer.
* **Fitness:** do not ship this. ★☆☆☆☆

#### 20. Knuth–Plass global optimizer over the whole book (programmatic TeX internals or a custom implementation) ★★★★★

The *correct* way, in the Knuth-ian sense. Formulate the book as a constrained optimization: minimize a penalty function over (line break positions, page break positions, note placements, widows/orphans, column balance, spillover depth) subject to:

* each footnote's reference is on the same page as the footnote body,
* no orphan/widow lines,
* chapter openers start a new page,
* the ornament is on the last page of a chapter only,
* column heights differ by at most *h*.

Solve with dynamic programming (what TeX's line-breaker does for lines, extended to 2D pages). Render with HarfBuzz + cairo.

* **Wins:** provably optimal layout. Handles any book with the same rules. This is what a TeX-like engine does internally.
* **Breaks:** you're building the successor to TeX. Years of work, but the algorithm itself is well-documented since Knuth 1981.
* **Fitness:** the honest answer for "most advanced approach." In practice, Typst (#8) is the shortest path to 80% of this result. ★★★★★ intellectually, ★★★☆☆ practically.

---

## Part III — Comparison matrix and recommendations

### 3.1 At-a-glance comparison

| # | Approach | RTL / Hebrew | Floating footnotes | 2-col + spillover | Dev effort | Output fidelity |
|---:|---|:---:|:---:|:---:|:---:|:---:|
| 1 | Pure CSS paged media | ✅ | ❌ | ❌ | 1 day | 40% |
| 2 | **Paged.js** | ✅ | ✅ | 🟡 plugin | 1 week | 85% |
| 3 | Vivliostyle | ✅ | ✅ | 🟡 plugin | 1 week | 85% |
| 4 | Pandoc + XeLaTeX | ✅ | ✅ | ⚠️ manual | 2 weeks | 75% |
| 5 | ReportLab Platypus | 🟡 bidi hack | ✅ (manual) | ✅ frames | 2 weeks | 85% |
| 6 | WeasyPrint | ✅ | 🟡 basic | ❌ | 3 days | 60% |
| 7 | Prince XML | ✅ | ✅ | 🟡 mostly | 3 days | 90% |
| 8 | **Typst** | ✅ | ✅ | ✅ custom fn | 1 week | 90% |
| 9 | XeLaTeX + Memoir + manyfoot | ✅ | ✅ (2 streams) | 🟡 manual | 3 weeks | 90% |
| 10 | LuaLaTeX + callbacks | ✅ | ✅ | ✅ scripted | 4 weeks | 95% |
| 11 | ConTeXt | ✅ | ✅ | 🟡 | 3 weeks | 90% |
| 12 | **InDesign + IDML** | ✅ | ✅ | ✅ | 1–2 days/book, not automated | 100% |
| 13 | QuarkXPress | ✅ | ✅ | ✅ | same as IDML | 100% |
| 14 | HarfBuzz + cairo custom | ✅ | DIY | DIY | months | 95% |
| 15 | PDFKit / pdf-lib | 🟡 | DIY | DIY | weeks | 70% |
| 16 | SVG per-page | ✅ | DIY | DIY | weeks | 80% |
| 17 | **LLM planner + renderer** | depends | derived | derived | 3 days | 85% |
| 18 | OCR + RL | ❌ unneeded | — | — | months | single-book |
| 19 | Diffusion/VLM | ❌ | — | — | days | 20% |
| 20 | Knuth–Plass global | ✅ | ✅ | ✅ | years | 100% |

### 3.2 Recommended paths by goal

* **Fastest usable result (weekend):** **Paged.js** (#2). Pre-partition notes into "column-right / column-left / spillover" buckets in Node before handing HTML to Paged.js. Ship the PDF from a headless Chromium.
* **Best quality-to-effort ratio (1–2 weeks):** **Typst** (#8). Model each page as a block with `place()` calls and a custom `note-block(right, left)` function that handles the spillover. Hebrew + RTL is one `set text(dir: rtl, font: "SBL Hebrew")` line.
* **Best quality if you own a license:** **Prince XML** (#7) or **Adobe InDesign** (#12). Prince if you want it automated from the JSON; InDesign if you're laying out one prestige edition by hand.
* **Best investment if you're publishing a catalogue:** **XeLaTeX + Memoir + manyfoot** (#9). Write the preamble once, feed it structured Markdown per sefer. It's how most academic Hebrew books have been typeset for 20 years.
* **Most interesting research direction:** **LLM planner + deterministic renderer** (#17). Closest thing to how a human typesetter thinks ("paragraphs 3 and 4 should go on page 7, with footnote ח spilling over") while staying reproducible.

### 3.3 The exact rule-set a renderer must implement

Copy-paste checklist for whichever engine you pick:

1. Parse JSON; classify each `docx_content[i].text` into one of `{chapter, chapter-title, subtitle, body, ornament}`.
2. Parse inline `[א]`, `[ב]`… tokens in body text, replace with superscript call-outs, and pair each call-out with `footnotes[i]` positionally.
3. Do the same for endnote call-outs, paired with `endnotes[i]`.
4. Configure page: **170 × 240 mm, RTL, margins ~20 mm top/outer, 25 mm inner/bottom**.
5. Header: folio letter (gematria counter that starts at **77**), centered `שפע`, chapter label on opener pages / *shaar* label (`שער ההודאה`) on interior pages, `שלמה`.
6. Footer: none.
7. Body frame: starts ~40 mm from top on chapter openers (to clear cartouche), ~20 mm on interior pages. Justified, 12–13 pt Hebrew serif (e.g. *Frank Rühl*, *David Libre*, *Narkisim*, or *SBL Hebrew*).
8. Drop-letter: body paragraph's leading `א. / ב.` is bolded at 1.4× body size.
9. Notes block below the body: max height = 40% of page. Two columns (RTL = right first), gutter ~24 pt. Rule-headers `═══ מקור השפע ═══` (right) and `═══ צינור השפע ═══` (left); render left header only if endnotes present.
10. Spillover: when either column cannot contain its full text, push the remainder (right-column first, then left-column) into a single full-width zone beneath the columns at the same smaller point size.
11. Constraint: **if a body paragraph contains call-out `[x]`, the corresponding footnote/endnote must render on the same page.** If it can't, break the body earlier.
12. Chapter-ending ornament: on the last page of each chapter, center the winged glyph horizontally in the remaining whitespace above the notes zone (or, if no notes, in the lower third of the page).
13. Blank verso before an appendix/cover where needed (page 123 in the sample is intentionally blank because the back cover was pinned to the next recto).
14. Back cover: full-bleed image with publisher logo centered (not text-flow).

### 3.4 My recommendation, if you were to start tomorrow

Pick **Typst** (#8) and spend a week. It handles every hard rule above declaratively, compiles in under a second, and the source code will be readable by the next developer. Wire up a small Python pre-processor that turns your JSON into Typst source with inline `#footnote[...]` and `#endnote[...]` calls, then write one `note-apparatus()` function that packs the two columns and emits spillover. You'll be 90% of the way to PDF-parity with the reference pages, and you'll have source you can version-control for every future title.

If instead you need to ship *today* with minimum learning curve, do **Paged.js** (#2) with a pre-partitioning step in Node. The output will be 85% of the way there and can be refined with CSS alone.

And if you're ever willing to hand-tune one book, open **InDesign** (#12) and do it properly — but keep that workflow out of your pipeline.

---

*Prepared from measurements taken directly from the supplied JSON (51 blocks, 42,531 characters) and visual analysis of PDF pages 105–124.*
