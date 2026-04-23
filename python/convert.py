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
import re
import sys
import unicodedata
from pathlib import Path
from typing import Dict, List


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
# Body rendering: emit #fn-col / #en-col / #fn-spill / #en-spill calls per
# block. Per-block pre-partition (M2 Path A) routes overflow into the full-
# width spillover zone so the 2-col apparatus never runs beyond its
# reserved height.
# ---------------------------------------------------------------------------
def render_body(block: dict) -> "tuple[str, int, int, int]":
    """Convert a body block's text into Typst source with trailing note
    call-outs, pre-partitioned by M2's column-capacity rule.

    The source JSON (DOCX-extracted) does NOT carry inline bracket markers
    like `[א]` in body text — verified empirically on
    source_uploads/docx_content_with_notes.json. Therefore we cannot
    re-anchor call-outs by regex position as previous pipelines attempted
    (which silently dropped all 24 footnotes and all 10 endnotes).

    M1 strategy: append one #fn[body] / #en[body] call per entry in
    footnote_refs / endnote_refs, in list order. Each call wraps the note
    body whose `id` equals the corresponding ref element. This preserves
    the ordering invariant required by VAL-M1-013 (k-th marker ↔ k-th ref).

    M2 extension: each block's fn and en streams are partitioned by
    ``_partition_stream`` into a column-fitting prefix and a spillover
    remainder. The emission order per block is:

        fn-col[...]  fn-col[...]  ...
        en-col[...]  en-col[...]  ...
        fn-spill[...] fn-spill[...] ...
        en-spill[...] en-spill[...] ...

    The Typst-side apparatus queries all footnotes on the current render
    page, partitions by metadata zone tag, and renders the 2-col grid for
    col notes plus a full-width spillover row for spill notes (fn overflow
    first, then en overflow — stream order, VAL-M2-003).

    If a ref id has no matching entry in footnotes[]/endnotes[], we
    print a WARN line to stderr and skip it — surfacing future corpus
    drift instead of silently dropping notes. The skipped count is
    returned so the CLI can include it in the summary line.

    Returns (rendered_source, fn_emitted_count, en_emitted_count, refs_skipped).
    """
    text = block["text"]
    idx = block.get("index", "?")
    fn_by_id = {str(f["id"]): f["text"] for f in (block.get("footnotes") or [])}
    en_by_id = {str(e["id"]): e["text"] for e in (block.get("endnotes") or [])}
    fn_refs = [str(r) for r in (block.get("footnote_refs") or [])]
    en_refs = [str(r) for r in (block.get("endnote_refs") or [])]

    fn_col, fn_spill, fn_skipped = _partition_stream(
        fn_refs, fn_by_id, COL_CAPACITY_CHARS,
    )
    en_col, en_spill, en_skipped = _partition_stream(
        en_refs, en_by_id, COL_CAPACITY_CHARS,
    )

    # Mirror the M1 per-skipped-ref WARN line so stderr stays informative
    # under partial corpus drift.
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

    out_parts: List[str] = [escape_typst(text)]

    # Emit order per block: fn-col → en-col → fn-spill(+cont) →
    # en-spill(+cont). This order keeps the column content ahead of the
    # spillover content in doc order, matching the natural reading flow
    # of the page apparatus (col grid above, spillover below). Split-
    # note continuations ride along in the spill bucket as
    # ``spill-cont`` entries — the Typst wrapper (#fn-spill-cont /
    # #en-spill-cont) tags them so the apparatus knows to render them
    # marker-less, preserving the "one visible marker per note" rule.
    def _wrapper(stream: str, kind: str) -> str:
        if kind == "col":
            return f"{stream}-col"
        if kind == "spill":
            return f"{stream}-spill"
        if kind == "spill-cont":
            return f"{stream}-spill-cont"
        raise ValueError(f"unknown note kind: {kind!r}")

    for _, body_text, kind in fn_col:
        esc = escape_typst(body_text).replace("\n", " ")
        out_parts.append(f"#{_wrapper('fn', kind)}[{esc}]")
    for _, body_text, kind in en_col:
        esc = escape_typst(body_text).replace("\n", " ")
        out_parts.append(f"#{_wrapper('en', kind)}[{esc}]")
    for _, body_text, kind in fn_spill:
        esc = escape_typst(body_text).replace("\n", " ")
        out_parts.append(f"#{_wrapper('fn', kind)}[{esc}]")
    for _, body_text, kind in en_spill:
        esc = escape_typst(body_text).replace("\n", " ")
        out_parts.append(f"#{_wrapper('en', kind)}[{esc}]")

    fn_emitted = len(fn_col) + len(fn_spill)
    en_emitted = len(en_col) + len(en_spill)
    refs_skipped = fn_skipped + en_skipped

    return "".join(out_parts), fn_emitted, en_emitted, refs_skipped


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
) -> "tuple[str, int, int, int]":
    """Emit the full Typst source for the book.

    Returns (source_text, total_fn_emitted, total_en_emitted, refs_skipped).

    The plain-text fallback (``build/book.plain.txt``) is NOT emitted from
    this converter. It is produced Typst-side via ``<plain-line>`` metadata
    tags in ``typst/template.typ`` so the witness reflects what the
    template *actually* renders rather than what the JSON source
    prescribes. See services.yaml::commands.build-plain-text.
    """
    blocks = data["docx_content"]

    out: List[str] = [
        TEMPLATE_PROLOGUE.format(
            template_path=template_path,
            shaar=shaar,
            start_folio=start_folio,
        )
    ]

    total_fn = 0
    total_en = 0
    total_skipped = 0

    # Buffer chapter opener (label + title together).
    pending_chapter: str | None = None

    for block in blocks:
        kind = classify(block["text"])
        txt = block["text"].strip()

        if kind == "chapter":
            pending_chapter = txt
            continue

        if kind == "chapter_title":
            label = pending_chapter or ""
            pending_chapter = None
            out.append(
                f"#chapter([{escape_typst(label)}], [{escape_typst(txt)}])\n"
            )
            continue

        if pending_chapter is not None:
            # Chapter label without the expected vowelised title.
            out.append(f"#chapter([{escape_typst(pending_chapter)}], [])\n")
            pending_chapter = None

        if kind == "subtitle":
            out.append(f"#subtitle([{escape_typst(txt)}])\n")
            continue

        if kind == "ornament":
            out.append("#ornament()\n")
            continue

        # body
        rendered, fn_n, en_n, skipped = render_body(block)
        total_fn += fn_n
        total_en += en_n
        total_skipped += skipped
        out.append("#body[\n")
        out.append(rendered)
        out.append("\n]\n\n")

    if pending_chapter is not None:
        out.append(f'#chapter([{escape_typst(pending_chapter)}], [])\n')

    return "".join(out), total_fn, total_en, total_skipped


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

    src, total_fn, total_en, total_skipped = convert(
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


if __name__ == "__main__":
    main()
