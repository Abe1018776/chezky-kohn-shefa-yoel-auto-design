#!/usr/bin/env python3
"""
JSON -> Typst converter for the Shefa Shlomo sefer pipeline.

Input:  source_uploads/docx_content_with_notes.json
Output: build/book.typ  (imports ../typst/template.typ)

Usage:
    python3 python/convert.py \
        --in source_uploads/docx_content_with_notes.json \
        --out build/book.typ \
        --template typst/template.typ \
        --shaar "שער ההודאה" \
        --start-folio 77
"""
from __future__ import annotations

import argparse
import json
import math
import re
import sys
import unicodedata
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Classification (derived from pagination_study.md §1.1)
# ---------------------------------------------------------------------------
NIQQUD_RANGE = range(0x0591, 0x05C8)
CHAPTER_RE = re.compile(r"^פרק\s+\S+$")
BODY_START_RE = re.compile(r"^[\u05D0-\u05EA]\.\s")


def has_niqqud(s: str) -> bool:
    return any(ord(c) in NIQQUD_RANGE for c in s)


def classify(text: str) -> str:
    t = text.strip()
    if t == "*":
        return "ornament"
    if CHAPTER_RE.match(t) and len(t) <= 8:
        return "chapter"
    if has_niqqud(t) and len(t) <= 60:
        return "chapter_title"
    if BODY_START_RE.match(t):
        return "body"
    if len(t) <= 90 and not BODY_START_RE.match(t):
        return "subtitle"
    return "body"


# ---------------------------------------------------------------------------
# Typst string / content escaping
# ---------------------------------------------------------------------------
# Characters that must be escaped inside a Typst content block.
_TYPST_SPECIALS = {
    "\\": r"\\",
    "#":  r"\#",
    "$":  r"\$",
    "*":  r"\*",
    "_":  r"\_",
    "`":  r"\`",
    "<":  r"\<",
    ">":  r"\>",
    "@":  r"\@",
    "=":  r"\=",
    "~":  r"\~",
    "[":  r"\[",
    "]":  r"\]",
}


def escape_typst(s: str) -> str:
    # Preserve Hebrew and niqqud as-is; escape only Typst syntax chars.
    return "".join(_TYPST_SPECIALS.get(c, c) for c in s)


# ---------------------------------------------------------------------------
# M2 — column-capacity constant used to pre-partition note bodies into the
# 2-col apparatus vs. the full-width spillover row (Path A from the M2
# mission spec, see source_uploads/pagination_study.md §1.3).
#
# At PFT_Vilna 9pt in a ~58.5mm-wide column (half of the 125mm text block
# minus the 8mm gutter), roughly 30–35 Hebrew chars fit per line. The
# pre-reserved 85mm bottom margin (see typst/template.typ::book) hosts the
# rule-headers (~8mm), the 2-col grid (up to ~45mm), and the full-width
# spillover row (remainder, ~30mm — ~60 chars/line × ~6 lines ≈ 360 chars
# of comfortable capacity). Capping each column at 650 chars keeps the
# 2-col grid within ~45mm so the spillover row always has room to appear
# on the same page without pushing content off the page bottom.
#
# The constant is intentionally coarse: Hebrew char widths vary, and
# niqqud/tracking affect the real line count slightly. Tune empirically by
# observing the rendered PNGs. See VAL-M2-002 (spillover existence),
# VAL-M2-005 (page count stability), VAL-M2-010 (body-position
# stability), and VAL-M2-011 (longest-note single-page rendering).
# ---------------------------------------------------------------------------
# Character threshold for routing a single note into col-head +
# full-width spillover. Matches round-1's 1500-char threshold, which
# was tuned against the M1 reference scans.
COL_CAPACITY_CHARS = 1500


def _split_body(body: str, at: int) -> "tuple[str, str]":
    """Split a note body near character offset ``at`` on a word boundary.

    Hebrew body text uses standard ASCII spaces between words. We look
    for the first space at or after ``at`` — if found within a
    reasonable distance of the end of the body, we split there;
    otherwise we scan backward for the last space before ``at``. If no
    suitable boundary exists, we split at the raw offset (rare for
    Hebrew paragraphs).

    Returns ``(head, tail)``. Both are non-empty when the split actually
    happens; ``tail`` is an empty string if ``at >= len(body)``.
    """
    if at >= len(body):
        return body, ""
    # Prefer a space AT or AFTER `at` (keeps col content at or above the
    # nominal capacity) — but not so far that the split leaves a tiny
    # tail.
    forward = body.find(" ", at)
    if forward != -1 and forward <= len(body) - 80:
        return body[:forward].rstrip(), body[forward:].lstrip()
    # Fallback: scan backward for the most recent space before `at`.
    backward = body.rfind(" ", 0, at)
    if backward != -1 and backward >= 80:
        return body[:backward].rstrip(), body[backward:].lstrip()
    # Last resort — split at raw offset.
    return body[:at], body[at:]


def _partition_stream(
    refs: List[str],
    by_id: Dict[str, str],
    capacity: int,
) -> "tuple[list, list, int]":
    """Split a block's fn or en stream into col[] and spill[] entries.

    Scans ``refs`` in JSON order. The FIRST note in each stream is always
    anchored to ``col`` (or at least its opening portion is) so that
    VAL-M2-008 holds: spillover never appears on a page without at
    least one column note. The partition rules are:

    1. If the first note's body is ≤ ``capacity`` chars, it lands
       wholly in ``col`` and the used budget advances accordingly.
    2. If the first note's body is > ``capacity`` chars, it is SPLIT at
       a word boundary near ``capacity``:  the head portion (with the
       original note marker) lands in ``col``, and the tail flows into
       ``spill`` as a marker-less continuation — reference_scans/page_117
       (Rebbe of Radomsk, endnote id "3") shows this split/continuation
       pattern in the printed edition. The continuation is tagged
       ``"spill-cont"`` so the Typst apparatus suppresses its marker
       (the head's marker is the note's only marker).
    3. Subsequent notes: if cumulative ``used + len(body) ≤ capacity``,
       they join the column; otherwise that note and every remaining
       note goes into ``spill`` as a fresh entry (its own marker).

    Edge case (VAL-M2-011): block 4 en id "1" (~5,146 chars) produces a
    col-head + spill-cont pair that together render on a single page
    without truncation. Same for block 31 fn id "13" (~1,687 chars),
    block 48 fn id "22" (~1,551 chars), and the like.

    Refs that have no matching entry in ``by_id`` are skipped with a
    WARN to stderr (preserving the M1 behaviour); the return tuple's
    third element is the skipped-refs count.

    Each entry in ``col`` / ``spill`` is a tuple
    ``(ref_id, body_text, kind)`` where ``kind`` is one of:

      * ``"col"``       — regular column-zone note, gets a marker.
      * ``"spill"``     — regular spillover-zone note, gets a marker.
      * ``"spill-cont"``— continuation of a split first note, marker-
        less; lives in the spillover zone, rendered in doc order
        among fn/en spill notes.
    """
    col: List[tuple] = []
    spill: List[tuple] = []
    skipped = 0
    used = 0
    spilling = False
    first_seen = False
    for ref_id in refs:
        body = by_id.get(ref_id)
        if body is None:
            skipped += 1
            continue
        if not first_seen:
            # First note of this stream in this block.
            first_seen = True
            if len(body) <= capacity:
                col.append((ref_id, body, "col"))
                used = len(body)
            else:
                # Split: head to col (with marker), tail to spill as
                # marker-less continuation.
                head, tail = _split_body(body, capacity)
                col.append((ref_id, head, "col"))
                used = len(head)
                if tail:
                    spill.append((ref_id, tail, "spill-cont"))
                    # A continuation tail already occupies the
                    # spillover zone; flag ``spilling`` so any later
                    # notes flow to ``spill`` too (preserving note
                    # order within the block).
                    spilling = True
            continue
        if spilling or used + len(body) > capacity:
            spill.append((ref_id, body, "spill"))
            spilling = True
        else:
            col.append((ref_id, body, "col"))
            used += len(body)
    return col, spill, skipped


# ---------------------------------------------------------------------------
# M2 round-4 — block pair-keep pagination
#
# `python/convert.py` is the pagination authority. It pre-computes per-
# block (body + fn-col + fn-spill + en-col + en-spill) natural heights
# from char counts, accumulates them in reading order under a +15%
# safety margin, and inserts page breaks at block boundaries when the
# running page budget would be exceeded. Each page's emitted bottom
# margin is sized to the cumulative notes height of the blocks that
# land on it — so body TOP-y stays at top-margin but body BOTTOM-y
# varies per page by design.
#
# Orphan prevention:
#   * chapter_opener = (chapter label + chapter_title + following
#     subtitle + following body) is treated as a single keep-together
#     group — no split between the cartouche/title and the first body.
#   * subtitle + next body are a keep-together pair — a subtitle is
#     never the last non-note content on a page.
#   * ornament rides with the preceding group — never starts its own
#     page.
#
# Pair-keep invariant (VAL-M2-012): because a body block and ALL its
# fn/en notes are emitted inside the same `#page(margin: (bottom: Xmm))
# [...]` block, Typst's footnote engine always pins each note to the
# same physical page as its body reference. The only escape is a body
# longer than a single page's body budget — in which case body splits
# and the invariant applies per body-segment.
# ---------------------------------------------------------------------------

# Page geometry (matches typst/template.typ::book defaults)
PAGE_HEIGHT_MM = 240.0
TOP_MARGIN_MM = 22.0
INSIDE_MARGIN_MM = 25.0
OUTSIDE_MARGIN_MM = 20.0
FOOTER_DESCENT_MM = 6.0
MIN_BOTTOM_MARGIN_MM = 15.0  # folio footer only when page has no notes

# Body typography (PFT_Frank 16pt, leading 1.15em)
#   Measured line stride on reference build ≈ 6.5mm.
BODY_LINE_MM = 6.6
#   Hebrew body at 16pt fits roughly 42 chars in the 125mm text column.
BODY_CHARS_PER_LINE = 42

# Notes apparatus typography (PFT_Vilna 9pt, leading 0.58em, spacing 0.25em)
#   Calibrated from M2 round-1 page-1 rendering: the 9pt notes zone
#   occupied ~75mm and held ~27 lines of text across col+col+spillover
#   ⇒ ~2.8mm stride per line. PFT_Vilna is a dense Hebrew commentary
#   face; column width = (125 − 8)/2 = 58.5mm fits ~40 chars at 9pt,
#   full-width spillover fits ~115 chars (note: Hebrew glyph widths
#   average smaller than Latin, and the PFT_Vilna niqqud-bearing
#   variant is narrower still).
NOTES_LINE_MM = 2.8
NOTES_COL_CHARS_PER_LINE = 40
NOTES_SPILL_CHARS_PER_LINE = 115
#   Rule header bar + inter-row padding.
NOTES_HEADER_MM = 7.0
#   Gap between 2-col grid and full-width spillover row.
NOTES_SPILL_GAP_MM = 3.0
#   Per-note inter-entry gap (v(2pt) after each rendered note).
INTER_NOTE_MM = 1.0

# Pair-keep cap: even under the escape clause for blocks whose notes
# exceed a full page budget, we never emit a bottom margin larger than
# this — that would leave too little body area for opener/subtitle
# chrome to fit. Block 4 en#1 (5146 chars) is the exemplar: its notes
# cannot fit on one page at 9pt typography, so Typst's native footnote
# splitter takes over (footnote body continues on the next page).
MAX_BOTTOM_MARGIN_MM = 190.0

# Structural heights
#   subtitle(): v(2mm) + 10.5pt line (~3.7mm) + v(1mm)
SUBTITLE_MM = 8.0
#   chapter(): v(8mm) + cartouche (~26mm with padding) + v(4mm) + chapter_title
#   (20pt display line + tracking ~8mm) + v(8mm)
CHAPTER_OPENER_CHROME_MM = 56.0
#   ornament(): v(1fr) + 22pt glyph (~8mm) + v(1fr) — the glyph itself is
#   small; v(1fr) absorbs page whitespace, so for packing purposes the
#   minimum incompressible height is just the glyph + a little padding.
ORNAMENT_MM = 12.0

# Safety margin on estimates (round up for typographic variance). The
# paginator budgets ``height * HEIGHT_SAFETY`` per group, then asks for
# a per-page bottom margin of the same safety-adjusted amount. Too-low
# safety leaves Typst with less space than needed → the footnote
# engine splits ⇒ cross-page orphan notes (VAL-M2-012 violation). 1.15
# is slightly conservative but matches the behaviour under the
# reference scans.
HEIGHT_SAFETY = 1.15

# A page can accommodate at most PAGE_BUDGET_MM of body+notes content in
# total (the bottom margin shrinks/grows to fit the notes; body gets what
# remains above). Use the full page height minus the fixed top margin
# and the footer-descent reserve — the bottom margin is ENTIRELY given
# to the apparatus on heavy-notes pages, and the rule-header chrome is
# charged explicitly in _page_total_height.
PAGE_BUDGET_MM = PAGE_HEIGHT_MM - TOP_MARGIN_MM - FOOTER_DESCENT_MM  # ≈ 212


def _estimate_notes_height_mm(
    fn_col: list, fn_spill: list, en_col: list, en_spill: list
) -> float:
    """Estimate the vertical footprint of a block's NOTES CONTENT alone
    (no rule-header chrome — that's charged per-page in
    ``_page_notes_content_height``, since multiple blocks' notes share
    a single apparatus header on the same page).

    `fn_col` / `fn_spill` / `en_col` / `en_spill` are the tuples returned
    by `_partition_stream`: `(ref_id, body_text, kind)`.
    """
    if not (fn_col or fn_spill or en_col or en_spill):
        return 0.0

    def _count(entries: list, chars_per_line: int) -> Tuple[int, int]:
        if not entries:
            return 0, 0
        chars = sum(len(b) for (_, b, _) in entries)
        # Each note always consumes at least one line of its own; avoid
        # underestimating when short notes pack tightly with long ones.
        lines = max(len(entries), math.ceil(chars / chars_per_line))
        return lines, len(entries)

    # The two columns render independently — the taller one fixes the
    # grid height.
    fn_lines, fn_n = _count(fn_col, NOTES_COL_CHARS_PER_LINE)
    en_lines, en_n = _count(en_col, NOTES_COL_CHARS_PER_LINE)
    col_lines = max(fn_lines, en_lines)
    col_height = col_lines * NOTES_LINE_MM + (fn_n + en_n) * INTER_NOTE_MM

    spill_lines, spill_n = _count(
        fn_spill + en_spill, NOTES_SPILL_CHARS_PER_LINE
    )
    spill_height = spill_lines * NOTES_LINE_MM + spill_n * INTER_NOTE_MM

    total = col_height
    if spill_height > 0:
        total += NOTES_SPILL_GAP_MM + spill_height
    return total


def _estimate_body_height_mm(text: str) -> float:
    """Estimate the vertical footprint of a body paragraph in mm."""
    char_count = len(text)
    if not char_count:
        return 0.0
    lines = max(1, math.ceil(char_count / BODY_CHARS_PER_LINE))
    return lines * BODY_LINE_MM


# ---------------------------------------------------------------------------
# Render-block dataclass — a single typeset unit in reading order.
# ---------------------------------------------------------------------------
@dataclass
class RenderBlock:
    kind: str  # 'chapter', 'chapter_title', 'subtitle', 'body', 'ornament'
    src_index: int  # source JSON block index (1-based)
    text: str = ""
    # Chapter openers hold the label in `text` (for chapter) and the title
    # (for chapter_title) — the converter pairs them into a single
    # #chapter(label, title) emission via a pending_chapter buffer.
    # For body blocks, the note partition is stored here.
    fn_col: list = field(default_factory=list)
    en_col: list = field(default_factory=list)
    fn_spill: list = field(default_factory=list)
    en_spill: list = field(default_factory=list)
    fn_skipped: int = 0
    en_skipped: int = 0

    @property
    def body_height(self) -> float:
        """Body contribution to page top area (varies by block kind)."""
        if self.kind == "body":
            return _estimate_body_height_mm(self.text)
        if self.kind == "subtitle":
            return SUBTITLE_MM
        if self.kind == "chapter":
            # Chapter label alone contributes no body height — the
            # opener chrome is attached to chapter_title below so the
            # group total accounts for it exactly once.
            return 0.0
        if self.kind == "chapter_title":
            return CHAPTER_OPENER_CHROME_MM
        if self.kind == "ornament":
            return ORNAMENT_MM
        return 0.0

    @property
    def notes_height(self) -> float:
        """Notes-zone contribution (only non-zero for body blocks with notes)."""
        if self.kind != "body":
            return 0.0
        return _estimate_notes_height_mm(
            self.fn_col, self.fn_spill, self.en_col, self.en_spill
        )

    @property
    def body_line_count(self) -> int:
        """Number of body lines (used by VAL-M2-014 min-3-lines rule)."""
        if self.kind != "body" or not self.text:
            return 0
        return max(1, math.ceil(len(self.text) / BODY_CHARS_PER_LINE))


# ---------------------------------------------------------------------------
# Keep-together groups — atomic units the paginator cannot split.
# ---------------------------------------------------------------------------
@dataclass
class KeepGroup:
    blocks: List[RenderBlock]
    is_opener: bool = False  # chapter opener → always starts a new page

    @property
    def body_h(self) -> float:
        return sum(b.body_height for b in self.blocks)

    @property
    def notes_h(self) -> float:
        return sum(b.notes_height for b in self.blocks)

    @property
    def total_h(self) -> float:
        return self.body_h + self.notes_h

    @property
    def body_line_count(self) -> int:
        return sum(b.body_line_count for b in self.blocks)


def _build_render_blocks(raw_blocks: list) -> List[RenderBlock]:
    """Classify + (for bodies) pre-partition notes into a flat list of
    RenderBlock objects in JSON reading order.
    """
    out: List[RenderBlock] = []
    for block in raw_blocks:
        idx = block.get("index", 0)
        txt = block.get("text", "").strip()
        kind = classify(txt)
        if kind in ("chapter", "chapter_title", "subtitle", "ornament"):
            out.append(RenderBlock(kind=kind, src_index=idx, text=txt))
            continue
        # body: pre-partition fn/en streams
        fn_by_id = {
            str(f["id"]): f["text"] for f in (block.get("footnotes") or [])
        }
        en_by_id = {
            str(e["id"]): e["text"] for e in (block.get("endnotes") or [])
        }
        fn_refs = [str(r) for r in (block.get("footnote_refs") or [])]
        en_refs = [str(r) for r in (block.get("endnote_refs") or [])]
        fn_col, fn_spill, fn_skipped = _partition_stream(
            fn_refs, fn_by_id, COL_CAPACITY_CHARS
        )
        en_col, en_spill, en_skipped = _partition_stream(
            en_refs, en_by_id, COL_CAPACITY_CHARS
        )
        # WARN on missing refs (matching M1 behaviour).
        for ref_id in fn_refs:
            if ref_id not in fn_by_id:
                print(
                    f"convert: WARN: block {idx}: missing fn ref id={ref_id}",
                    file=sys.stderr,
                )
        for ref_id in en_refs:
            if ref_id not in en_by_id:
                print(
                    f"convert: WARN: block {idx}: missing en ref id={ref_id}",
                    file=sys.stderr,
                )
        out.append(
            RenderBlock(
                kind="body",
                src_index=idx,
                text=txt,
                fn_col=fn_col,
                en_col=en_col,
                fn_spill=fn_spill,
                en_spill=en_spill,
                fn_skipped=fn_skipped,
                en_skipped=en_skipped,
            )
        )
    return out


def _build_keep_groups(render_blocks: List[RenderBlock]) -> List[KeepGroup]:
    """Collapse the flat block list into keep-together groups.

    Grouping rules (M2 round-4 orphan prevention):

    1. A chapter + its chapter_title + the following subtitle + the
       following body form a CHAPTER_OPENER group that always starts a
       new page.
    2. A subtitle + the following body form a (subtitle, body) pair
       that never splits — prevents a page ending on a bare subtitle.
    3. An ornament rides with the PRECEDING group (never starts a page
       of its own, never is orphaned).
    """
    groups: List[KeepGroup] = []
    i = 0
    n = len(render_blocks)
    pending_chapter: Optional[RenderBlock] = None

    while i < n:
        b = render_blocks[i]
        if b.kind == "chapter":
            pending_chapter = b
            i += 1
            continue
        if b.kind == "chapter_title":
            opener_blocks: List[RenderBlock] = []
            if pending_chapter is not None:
                opener_blocks.append(pending_chapter)
                pending_chapter = None
            opener_blocks.append(b)
            i += 1
            if i < n and render_blocks[i].kind == "subtitle":
                opener_blocks.append(render_blocks[i])
                i += 1
            if i < n and render_blocks[i].kind == "body":
                opener_blocks.append(render_blocks[i])
                i += 1
            groups.append(KeepGroup(blocks=opener_blocks, is_opener=True))
            continue
        if b.kind == "subtitle":
            pair = [b]
            i += 1
            if i < n and render_blocks[i].kind == "body":
                pair.append(render_blocks[i])
                i += 1
            groups.append(KeepGroup(blocks=pair))
            continue
        if b.kind == "body":
            groups.append(KeepGroup(blocks=[b]))
            i += 1
            continue
        if b.kind == "ornament":
            # Ornament always rides with the preceding group — never an
            # orphan. If there's no preceding group (unlikely), put it
            # in its own group.
            if groups:
                groups[-1].blocks.append(b)
            else:
                groups.append(KeepGroup(blocks=[b]))
            i += 1
            continue
        i += 1

    if pending_chapter is not None:
        # Stray chapter label with no title — emit alone as opener so it
        # at least renders; highly unlikely in well-formed input.
        groups.append(
            KeepGroup(blocks=[pending_chapter], is_opener=True)
        )

    return groups


def _page_total_height(
    page_groups: List[KeepGroup], safety: float = HEIGHT_SAFETY
) -> float:
    """Safety-adjusted total height (body + notes + rule-header chrome)."""
    body = sum(g.body_h for g in page_groups)
    notes_content = sum(g.notes_h for g in page_groups)
    chrome = NOTES_HEADER_MM if notes_content > 0 else 0.0
    return (body + notes_content) * safety + chrome


def _page_notes_budget_mm(page_groups: List[KeepGroup]) -> float:
    """Maximum NOTES area this page's committed body can afford.

    The apparatus zone is whatever space remains after the body + top
    margin + footer-descent reserve. It MUST include the rule-header
    chrome — that's part of the apparatus footprint Typst sees.
    """
    body = sum(g.body_h for g in page_groups) * HEIGHT_SAFETY
    return PAGE_HEIGHT_MM - TOP_MARGIN_MM - body - FOOTER_DESCENT_MM - 5.0


def _paginate(
    groups: List[KeepGroup],
    budget_mm: float = PAGE_BUDGET_MM,
    safety: float = HEIGHT_SAFETY,
) -> List[List[KeepGroup]]:
    """First-fit bin-packing of keep-groups into pages.

    A page is closed (and a new one started) when either:
      * the next group is a chapter opener (openers always start a page),
      * adding the group would push the safety-adjusted page total over
        budget (body + notes + header chrome in the combined footprint), or
      * adding the group would leave the NOTES zone unable to fit the
        committed notes (notes_content + header chrome > remaining
        space after body). This constraint prevents the Typst layout
        engine from flowing notes onto a next page, which would break
        both the pair-keep invariant and the page count.
    We recompute the page-total (rather than just adding individual
    group heights) so the notes-header chrome is charged exactly once
    per page.
    """
    pages: List[List[KeepGroup]] = []
    cur: List[KeepGroup] = []

    def would_overflow(trial: List[KeepGroup]) -> bool:
        if _page_total_height(trial, safety) > budget_mm:
            return True
        notes_content = _page_notes_content_height(trial)
        if notes_content <= 0:
            return False
        notes_needed = notes_content * safety + FOOTER_DESCENT_MM + 2.0
        # If even a SINGLE block's notes can't fit in a fresh page, the
        # pair-keep escape clause applies and we accept the page; only
        # reject the would-add when the current page already holds
        # something.
        return notes_needed > _page_notes_budget_mm(trial)

    for g in groups:
        if g.is_opener and cur:
            pages.append(cur)
            cur = [g]
            continue
        trial = cur + [g]
        if cur and would_overflow(trial):
            pages.append(cur)
            cur = [g]
            continue
        cur = trial
    if cur:
        pages.append(cur)
    return pages


def _render_block_typst(rb: RenderBlock) -> str:
    """Emit Typst source for a single RenderBlock."""
    if rb.kind == "subtitle":
        return f"#subtitle([{escape_typst(rb.text)}])\n"
    if rb.kind == "ornament":
        return "#ornament()\n"
    if rb.kind == "chapter":
        # chapter label alone — only emitted if no following
        # chapter_title existed (degenerate case). The normal case is
        # handled via the opener_group renderer below.
        return f"#chapter([{escape_typst(rb.text)}], [])\n"
    if rb.kind == "chapter_title":
        # chapter_title alone — degenerate; pair it with an empty label.
        return f"#chapter([], [{escape_typst(rb.text)}])\n"
    if rb.kind == "body":
        return _render_body_typst(rb)
    return ""


def _render_body_typst(rb: RenderBlock) -> str:
    """Emit `#body(src: N)[text #fn-col(src: N)[...] ...]` for a body block.

    Emission order per block: fn-col → en-col → fn-spill(+cont) →
    en-spill(+cont). This matches the visual reading order of the page
    apparatus (col grid above, spillover below) and satisfies VAL-M2-003
    (fn overflow precedes en overflow).
    """
    out: List[str] = []
    out.append(f"#body(src: {rb.src_index})[\n")
    out.append(escape_typst(rb.text))

    def _wrapper(stream: str, kind: str) -> str:
        if kind == "col":
            return f"{stream}-col"
        if kind == "spill":
            return f"{stream}-spill"
        if kind == "spill-cont":
            return f"{stream}-spill-cont"
        raise ValueError(f"unknown note kind: {kind!r}")

    for _, body_text, kind in rb.fn_col:
        esc = escape_typst(body_text).replace("\n", " ")
        out.append(
            f"#{_wrapper('fn', kind)}(src: {rb.src_index})[{esc}]"
        )
    for _, body_text, kind in rb.en_col:
        esc = escape_typst(body_text).replace("\n", " ")
        out.append(
            f"#{_wrapper('en', kind)}(src: {rb.src_index})[{esc}]"
        )
    for _, body_text, kind in rb.fn_spill:
        esc = escape_typst(body_text).replace("\n", " ")
        out.append(
            f"#{_wrapper('fn', kind)}(src: {rb.src_index})[{esc}]"
        )
    for _, body_text, kind in rb.en_spill:
        esc = escape_typst(body_text).replace("\n", " ")
        out.append(
            f"#{_wrapper('en', kind)}(src: {rb.src_index})[{esc}]"
        )

    out.append("\n]\n")
    return "".join(out)


def _render_opener_typst(group: KeepGroup) -> str:
    """Emit `#chapter(label, title)` + following subtitle + body."""
    label_block: Optional[RenderBlock] = None
    title_block: Optional[RenderBlock] = None
    rest: List[RenderBlock] = []
    for b in group.blocks:
        if b.kind == "chapter" and label_block is None:
            label_block = b
        elif b.kind == "chapter_title" and title_block is None:
            title_block = b
        else:
            rest.append(b)

    label = escape_typst(label_block.text) if label_block else ""
    title = escape_typst(title_block.text) if title_block else ""
    out: List[str] = [f"#chapter([{label}], [{title}])\n"]
    for b in rest:
        out.append(_render_block_typst(b))
    return "".join(out)


def _render_group_typst(group: KeepGroup) -> str:
    if group.is_opener:
        return _render_opener_typst(group)
    return "".join(_render_block_typst(b) for b in group.blocks)


def _page_notes_content_height(page_groups: List[KeepGroup]) -> float:
    """Sum notes content height across all blocks on a page. The rule-
    header is a PER-PAGE chrome, not per-block, so we add it here once
    when at least one block contributes notes.
    """
    content = sum(g.notes_h for g in page_groups)
    if content <= 0:
        return 0.0
    return content + NOTES_HEADER_MM


def _page_bottom_margin_mm(page_groups: List[KeepGroup]) -> float:
    """Compute the bottom margin needed to host this page's notes zone.

    Invariant: body area must first fit the page's body content; the
    bottom margin is then sized to the committed notes height up to
    whatever space remains. If notes cannot fit in the remainder
    (one exemplar: block 4 en#1, 5146 chars), Typst's native footnote
    engine takes over and lets the apparatus continue onto the next
    page — pair-keep then breaks for that block, per the
    validation-contract escape clause.
    """
    body_needed = sum(g.body_h for g in page_groups) * HEIGHT_SAFETY
    notes_content = _page_notes_content_height(page_groups)

    # body area = PAGE_HEIGHT - TOP_MARGIN - bottom_margin, so the
    # largest bottom_margin we can afford while still fitting the body
    # is (PAGE_HEIGHT - TOP_MARGIN - body_needed). We also reserve a
    # small body slack to survive typographic underestimation.
    max_for_body = (
        PAGE_HEIGHT_MM - TOP_MARGIN_MM - body_needed - 5.0
    )
    max_for_body = max(MIN_BOTTOM_MARGIN_MM, max_for_body)
    max_for_body = min(MAX_BOTTOM_MARGIN_MM, max_for_body)

    if notes_content <= 0:
        return MIN_BOTTOM_MARGIN_MM

    needed = notes_content * HEIGHT_SAFETY + FOOTER_DESCENT_MM + 2.0
    return min(max_for_body, max(MIN_BOTTOM_MARGIN_MM, needed))


def _emit_page_blocks(pages: List[List[KeepGroup]]) -> Tuple[str, List[float]]:
    """Emit the per-page `#page(margin:...)[...]` source for all pages.

    Returns (source_text, list_of_bottom_margins_mm).
    """
    parts: List[str] = []
    bottoms: List[float] = []
    for page_groups in pages:
        bottom_mm = _page_bottom_margin_mm(page_groups)
        # Round up to 0.1mm for stable deterministic output.
        bottom_mm_rounded = math.ceil(bottom_mm * 10) / 10
        bottoms.append(bottom_mm_rounded)
        parts.append(
            "#page(margin: (top: "
            f"{TOP_MARGIN_MM:g}mm, bottom: {bottom_mm_rounded:g}mm, "
            f"inside: {INSIDE_MARGIN_MM:g}mm, outside: {OUTSIDE_MARGIN_MM:g}mm"
            "))[\n"
        )
        for g in page_groups:
            parts.append(_render_group_typst(g))
        parts.append("]\n\n")
    return "".join(parts), bottoms


def _count_emitted_notes(render_blocks: List[RenderBlock]) -> Tuple[int, int, int]:
    """Return (fn_entries, en_entries, refs_skipped)."""
    total_fn = sum(
        len(b.fn_col) + len(b.fn_spill) for b in render_blocks if b.kind == "body"
    )
    total_en = sum(
        len(b.en_col) + len(b.en_spill) for b in render_blocks if b.kind == "body"
    )
    total_skipped = sum(
        b.fn_skipped + b.en_skipped for b in render_blocks if b.kind == "body"
    )
    return total_fn, total_en, total_skipped


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
TEMPLATE_PROLOGUE = """\
#import "{template_path}": book, chapter, subtitle, body, ornament, fn-col, en-col, fn-spill, en-spill, fn-spill-cont, en-spill-cont

#show: book.with(shaar: "{shaar}", start-folio: {start_folio})

"""


def convert(
    data: dict,
    template_path: str,
    shaar: str,
    start_folio: int,
) -> "tuple[str, int, int, int, list]":
    """Emit the full Typst source for the book under M2 round-4 pair-keep
    pagination.

    Returns
        ``(source_text, total_fn, total_en, refs_skipped, pages)`` where
        ``pages`` is a list of per-page dicts
        ``{"bottom_mm": float, "group_count": int,
           "body_lines": int, "notes_h_mm": float,
           "block_indices": [...], "is_opener": bool}``
        useful for post-convert diagnostics.

    The plain-text fallback (``build/book.plain.txt``) is NOT emitted from
    this converter. It is produced Typst-side via ``<plain-line>`` metadata
    tags in ``typst/template.typ`` so the witness reflects what the
    template *actually* renders rather than what the JSON source
    prescribes. See services.yaml::commands.build-plain-text.
    """
    blocks = data["docx_content"]

    # 1. Classify + pre-partition notes per body block.
    render_blocks = _build_render_blocks(blocks)

    # 2. Collapse into keep-together groups (orphan prevention).
    groups = _build_keep_groups(render_blocks)

    # 3. First-fit bin-packing onto pages under +15% safety margin.
    pages = _paginate(groups)

    # 4. Emit per-page Typst blocks with per-page bottom-margin overrides.
    body_source, bottoms = _emit_page_blocks(pages)

    # 5. Assemble the full source.
    out: List[str] = [
        TEMPLATE_PROLOGUE.format(
            template_path=template_path,
            shaar=shaar,
            start_folio=start_folio,
        ),
        body_source,
    ]

    total_fn, total_en, total_skipped = _count_emitted_notes(render_blocks)

    # 6. Per-page diagnostics (used by CLI summary + post-build checks).
    page_info: list = []
    for page_groups, bottom_mm in zip(pages, bottoms):
        block_indices: List[int] = []
        body_lines = 0
        notes_h = 0.0
        is_opener_page = False
        for g in page_groups:
            if g.is_opener:
                is_opener_page = True
            for b in g.blocks:
                block_indices.append(b.src_index)
                body_lines += b.body_line_count
                notes_h += b.notes_height
        page_info.append(
            {
                "bottom_mm": round(bottom_mm, 2),
                "group_count": len(page_groups),
                "body_lines": body_lines,
                "notes_h_mm": round(notes_h, 2),
                "block_indices": block_indices,
                "is_opener": is_opener_page,
            }
        )

    return "".join(out), total_fn, total_en, total_skipped, page_info


def main() -> None:
    p = argparse.ArgumentParser()
    p.add_argument("--in", dest="inp",
                   default="source_uploads/docx_content_with_notes.json")
    p.add_argument("--out", dest="out",
                   default="build/book.typ")
    p.add_argument("--template", dest="template",
                   default="typst/template.typ")
    p.add_argument("--shaar", default="שער ההודאה")
    p.add_argument("--start-folio", type=int, default=77)
    args = p.parse_args()

    repo_root = Path(__file__).resolve().parent.parent
    inp = (repo_root / args.inp).resolve()
    out = (repo_root / args.out).resolve()
    tpl = (repo_root / args.template).resolve()
    out.parent.mkdir(parents=True, exist_ok=True)

    data = json.loads(inp.read_text(encoding="utf-8"))
    # Compute the template import path relative to the output file.
    try:
        rel_tpl = Path("..") / tpl.relative_to(repo_root)
    except ValueError:
        rel_tpl = tpl
    # In Typst, paths inside #import are relative to the source file.
    rel_tpl_for_out = Path.relpath = None  # type: ignore
    # Use os.path.relpath for cross-platform correctness.
    import os
    rel_tpl_for_out = os.path.relpath(tpl, start=out.parent)

    src, total_fn, total_en, total_skipped, pages = convert(
        data,
        template_path=rel_tpl_for_out.replace("\\", "/"),
        shaar=args.shaar,
        start_folio=args.start_folio,
    )
    out.write_text(src, encoding="utf-8")
    print(f"wrote {out}  ({len(src)} chars)")
    print(
        f"emitted {total_fn} fn + {total_en} en "
        f"({total_skipped} refs skipped)"
    )
    print(f"pair-keep pagination: {len(pages)} pages")
    # Post-pagination sanity check: every non-opener body-bearing page
    # renders ≥ 3 body lines (VAL-M2-014). Print a WARN for violations
    # but do not abort — the downstream validator flags structurally
    # impossible cases (e.g. isolated ornament), and we want the build
    # to complete so the evidence is inspectable.
    for i, info in enumerate(pages, start=1):
        print(
            f"  page {i}: blocks={info['block_indices']} "
            f"body_lines={info['body_lines']} "
            f"notes_h={info['notes_h_mm']}mm "
            f"bottom_margin={info['bottom_mm']}mm "
            f"{'[opener]' if info['is_opener'] else ''}",
            file=sys.stderr,
        )
        if (
            not info["is_opener"]
            and info["body_lines"] > 0
            and info["body_lines"] < 3
        ):
            print(
                f"convert: WARN: page {i} has only {info['body_lines']} "
                f"body lines (VAL-M2-014 requires ≥ 3)",
                file=sys.stderr,
            )


if __name__ == "__main__":
    main()
