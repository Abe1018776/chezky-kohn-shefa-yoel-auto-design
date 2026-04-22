# Shefa Shlomo — Sefer-Layout Pipeline Architecture

> Reference baseline: **commit `e70f144`** (`Add phase-2 missions: 2-col notes,
> spillover, winged ornament`). Future workers should treat this document as
> the canonical high-level map; for implementation details, read the source.

---

## 1. System overview

The project is a one-shot **JSON → Typst → PDF → audit** pipeline that
typesets a Hebrew religious book (a *sefer*) so that the rendered pages match
the 20 reference scans in `reference_scans/` as closely as possible.

```
   source_uploads/docx_content_with_notes.json          (raw input)
          │
          ▼
   python/convert.py           ─── classifies 51 blocks, emits Typst calls
          │
          ▼
   build/book.typ              ─── generated Typst source
          │  #import "../typst/template.typ": book, chapter, subtitle,
          │                                  body, ornament, fn, en
          ▼
   typst compile --root . --font-path typst/fonts
          │
          ▼
   build/book.pdf  +  build/page-{n}.png
          │
          ▼
   audit/image_diff.py         ─── diff vs reference_scans/*.png
          │
          ▼
   build/audit_report.md  (score 0..100, target ≥ 80 at phase-2 end)
```

Inputs live in `source_uploads/`; typographic ground-truth lives in
`reference_scans/` (pages 105–124 of the printed edition). Nothing outside
`build/` is produced or mutated by the pipeline.

---

## 2. Components

| Path                          | Role |
|-------------------------------|------|
| `python/convert.py`           | JSON block classifier + Typst emitter. Walks `docx_content[]`, decides each block's semantic kind, and writes one `#chapter` / `#subtitle` / `#body[ … ]` / `#ornament()` call per block into `build/book.typ`. Also handles inline note call-outs inside body text. |
| `typst/template.typ`          | The layout DSL. Defines page size, RTL text defaults, Hebrew-gematria folio counter, running-header builder, cartouche + vowelised chapter title, footnote apparatus hooks, and the ornament glyph. All public symbols (`book`, `chapter`, `subtitle`, `body`, `ornament`, `fn`, `en`) are consumed by the converter's output. |
| `typst/fonts/`                | Vendored TTFs: `Shefa` (display), `PFT_Frank` (body), `PFT_Vilna` (notes), plus fallbacks. Picked up via `--font-path typst/fonts`. |
| `audit/image_diff.py`         | The validation scorer. Renders each Typst-produced `page-{n}.png` against the matching `reference_scans/page_{n}.png`, computes a weighted pixel/structure diff, and writes `build/audit_report.md` with a score. Used to gauge fidelity across missions. |
| `audit/paged/`                | Parallel track B scaffolding for a Paged.js (HTML+CSS GCPM) renderer. Not on the critical path of the Typst track but kept for cross-validation. |
| `reference_scans/page_*.png`  | Ground truth: PNGs of pages 105–124 of the printed sefer. Never mutated. |
| `source_uploads/docx_content_with_notes.json` | Raw classifier input (see §4). |
| `source_uploads/pagination_study.md`          | The authoritative hand-written typesetting spec (8 zones, classification rules, marker conventions). |
| `.factory/missions/m{1,2,3}-*`| Phase-2 mission directories (see §6). |

---

## 3. Data flow (detail)

1. **Load JSON.** `convert.py` reads `docx_content_with_notes.json` which has
   two top-level keys: `pdf_page_range_images` (unused by the converter) and
   `docx_content[]` — an ordered list of block objects.
2. **Classify each block.** `classify(text)` returns one of
   `chapter | chapter_title | subtitle | body | ornament` using the heuristics
   from `pagination_study.md §1.1` (asterisk → ornament, `פרק N` → chapter,
   niqqud + short → chapter_title, `א. ` prefix → body, else subtitle).
3. **Buffer chapter openers.** A `chapter` block's label is held until the
   next `chapter_title` block, then both are emitted together as
   `#chapter([label], [title])`.
4. **Render body.** For `body` blocks, `render_body(block)` walks the text
   looking for inline Hebrew-bracket call-outs (`[א]`, `[ב]`, …) and pairs
   them **positionally** with entries from `block.footnotes[]` then
   `block.endnotes[]`, emitting `#fn[…]` / `#en[…]` Typst calls inline.
5. **Compile Typst.** `template.typ`'s `book(...)` show-rule sets the page
   size (170 × 240 mm), RTL direction, fonts, gematria folio offset, and
   installs `show footnote.entry` + `set footnote.entry(separator: …)` hooks
   that render the `מקור השפע` rule-header and per-note style.
6. **Emit PDF and per-page PNGs** via two `typst compile` invocations.
7. **Audit.** `audit/image_diff.py` grids each rendered PNG against the
   corresponding reference scan and produces a composite score.

---

## 4. JSON input structure (inline note)

Top-level: `{ "pdf_page_range_images": [...], "docx_content": [51 blocks] }`.

Every block has the keys:
```
index, text, footnote_refs, endnote_refs, footnotes, endnotes
```
where `footnotes` / `endnotes` are lists of `{id, text}` objects and the
`_refs` arrays are parallel lists of the string ids.

Block-type census (`classify()` output on this file):

| Kind            | Count | Indices |
|-----------------|:-----:|---------|
| `chapter`       | 3     | 1, 26, 39 |
| `chapter_title` | 3     | 2, 27, 40 |
| `subtitle`      | 21    | 3, 5, 7, 9, 11, 13, 15, 17, 19, 21, 23, 28, 30, 32, 34, 36, 41, 43, 45, 47, 49 |
| `body`          | 21    | 4, 6, 8, 10, 12, 14, 16, 18, 20, 22, 24, 29, 31, 33, 35, 37, 42, 44, 46, 48, 50 |
| `ornament`      | 3     | 25, 38, 51 |

Notes coverage:

- **21 blocks** carry non-empty `footnotes[]`: indices 4, 6, 8, 10, 12, 14,
  16, 18, 20, 22, 24, 29, 31, 33, 35, 37, 42, 44, 46, 48, 50 — i.e. *every*
  body block has ≥ 1 footnote.
- **9 blocks** carry non-empty `endnotes[]`: 4, 6, 16, 18, 31, 35, 37, 48, 50.
- Totals: **24** footnote bodies and **10** endnote bodies across the file.
- In every sampled block, `footnote_refs` exactly mirrors the `id`s in
  `footnotes[]`, so id-based lookup is viable.

---

## 5. Key invariants

Any change must preserve these or the audit regresses visibly:

1. **Hebrew + RTL everywhere.** All text runs are emitted with
   `dir: rtl, lang: "he"`. Typst's `--font-path typst/fonts` must resolve
   before fallback fonts kick in.
2. **Gematria folio counter.** Page numbers are Hebrew letters, not digits.
   `hebrew-numeral(n)` covers 1..499 with the canonical `טו`/`טז`
   substitutions. The converter passes `--start-folio 77` so physical page 1
   prints as folio `עז`. The offset lives in `_folio-offset-state`.
3. **Per-chapter note counter reset.** Footnote numbering is keyed to
   Hebrew bracket markers (`[א]`, `[ב]`, …). Typst's built-in
   `counter(footnote)` increments globally; the sefer's convention is to
   restart per chapter. (Phase-2 missions inherit this requirement; see
   `pagination_study.md`.)
4. **Two-stream notes.** `#fn` → *מקור השפע* (right column, primary
   footnote) and `#en` → *צינור השפע* (left column, endnote-like stream).
   Both are pinned to the same page by Typst's footnote engine, but must be
   visually partitioned.
5. **8-zone page layout.** Header / cartouche / chapter-title / subtitle /
   body / 2-col notes / spillover / ornament — in that vertical order. Any
   intermediate pass must not reorder these zones.

---

## 6. Phase-2 missions at a glance

| ID | One-line summary |
|----|------------------|
| **M1** `m1-two-col-notes` | Split the single-stream footnote apparatus into **two columns**: מקור השפע (right) and צינור השפע (left) with independent heights and rule-headers. |
| **M2** `m2-full-width-spillover` | When the 2-column block overflows (e.g. the long Radomsk story on reference page 117), continue the overflow into a **full-width spillover zone** directly beneath the 2-column block. |
| **M3** `m3-winged-ornament` | Replace the placeholder `— ∞ —` end-of-chapter ornament with a **winged-cherub ornament** matching the reference scan. Parallelisable with M1/M2. |

Full mission contracts (`mission.md`, `validation-contract.md`,
`validation-state.json`) live under each `.factory/missions/m*/`.

---

## 7. Known quirks & gotchas

Future workers: **read this section before touching convert.py or the
notes-apparatus block in template.typ.** Both are load-bearing.

### 7.1 `convert.py` silently drops every `#fn[…]` call (critical bug)

- `render_body()` looks for inline call-outs with
  `CALLOUT_RE = re.compile(r"\[([\u05D0-\u05EA]{1,3})\]")` and, for each
  match, pops the next entry off `fn_queue` / `en_queue`.
- **The body text never contains any `[…]` bracket markers.** A whole-file
  scan of `docx_content_with_notes.json` finds **0** occurrences across
  all 21 body blocks (the only non-letter/non-space characters present in
  body text are `"`, `,`, and `.`). The Hebrew bracket markers seen in the
  reference scans were *stripped* during the DOCX → JSON extraction; the
  note-to-position information lives entirely in `footnote_refs` /
  `endnote_refs` (which in practice just mirror the `id`s).
- Consequently:
  - `CALLOUT_RE.finditer()` iterates zero times.
  - Zero `#fn[…]` calls are emitted → **all 24 footnote bodies are lost**.
  - The trailing-endnote fallback (`if en_used < len(en_queue)`) does fire,
    so the 10 endnote bodies do appear, dumped at the end of each paragraph.
- Any M1 implementation must first **re-introduce call-out markers** — either
  by re-anchoring the bracket letters at the start of the paragraph (crude),
  by re-synthesising positions from the footnote/endnote ref ordering
  (preferred), or by re-running extraction with markers preserved.

### 7.2 Typst `footnote.entry.separator` context cannot page-locate

The current template attaches the rule-header of the notes zone to
`set footnote.entry(separator: …)`:

```typst
set footnote.entry(
  separator: {
    v(6pt)
    grid(
      columns: (1fr, auto, 1fr),
      …
      pad(x: 8pt)[
        #set text(font: font-display, size: 9pt, dir: rtl,
                  tracking: 0.1em, fill: luma(25%))
        מקור השפע
      ],
      …
    )
    v(4pt)
  },
  clearance: 8mm,
  gap: 4pt,
  indent: 0pt,
)
```

- The `separator` block is content, not a `context` closure. Inside it you
  cannot call `here()`, query `counter(footnote).at(here())`, or otherwise
  look at *which page* this separator is rendering on.
- Concretely that means the separator cannot decide "this page has only
  endnotes, so print `צינור השפע` instead of `מקור השפע`", nor "this page
  has both, so stack two rule-headers", nor "this page has no notes at all
  — suppress".
- Any M1 two-stream split that tries to differentiate the two rule-headers
  *inside* the separator will hit this wall. The working solution is to
  bypass `footnote.entry.separator` entirely and lay the apparatus out via
  a custom `place(bottom)` or a page-level `show footnote.entry` hook that
  collects and partitions the live footnote stream (see the comment block in
  `template.typ` around `_note-rule` / `_is-endnote`, which was scaffolding
  toward exactly that redesign).

### 7.3 Other things to watch

- `_is-endnote(entry)` currently sniffs for `_en-label = "EN"` via
  `repr(entry.note.body)`. That's a fragile string-contains on the AST dump.
  If the metadata insertion changes, partitioning breaks silently.
- The ornament is a placeholder (`— ∞ —`); M3 replaces the glyph but must
  keep the `v(1fr)` flex above/below so chapter-end centering survives.
- `--start-folio 77` is passed at the CLI; do not hard-code the offset inside
  the template or the gematria counter will drift across chapter switches.
- The converter writes an import path computed by `os.path.relpath(tpl,
  start=out.parent)` — if you change the output location, the generated
  `#import "../typst/template.typ"` line changes with it. Keep this in mind
  when sandboxing.

---

## 8. What future workers should read next

1. `README.md` — phase-1 status and pipeline summary.
2. `source_uploads/pagination_study.md` — the actual typesetting spec.
3. `.factory/missions/m{1,2,3}-*/mission.md` — per-milestone goals.
4. `typst/template.typ` — the full layout DSL (only ~280 lines).
5. `python/convert.py` — the classifier + emitter.
6. `audit/image_diff.py` — how fidelity is scored.

Everything else (fonts, reference scans, audit scaffolding) is data or
tooling that does not need to be read to start a mission.
