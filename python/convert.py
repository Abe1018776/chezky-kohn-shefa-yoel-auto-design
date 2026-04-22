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
# Body rendering: emit #fn[] / #en[] calls in JSON footnote_refs / endnote_refs
# order and append them to the block's paragraph text.
# ---------------------------------------------------------------------------
def render_body(block: dict) -> "tuple[str, int, int, int]":
    """Convert a body block's text into Typst source with trailing
    #fn[...] and #en[...] calls.

    The source JSON (DOCX-extracted) does NOT carry inline bracket markers
    like `[א]` in body text — verified empirically on
    source_uploads/docx_content_with_notes.json. Therefore we cannot
    re-anchor call-outs by regex position as previous pipelines attempted
    (which silently dropped all 24 footnotes and all 10 endnotes).

    Strategy: append one #fn[body] call per entry in footnote_refs, in
    list order, followed by one #en[body] call per entry in endnote_refs,
    in list order. Each call wraps the note body whose `id` equals the
    corresponding ref element. This preserves the ordering invariant
    required by VAL-M1-013 (k-th marker ↔ k-th ref).

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

    out_parts: List[str] = [escape_typst(text)]
    fn_emitted = 0
    en_emitted = 0
    refs_skipped = 0

    for ref_id in fn_refs:
        body_text = fn_by_id.get(ref_id)
        if body_text is None:
            print(
                f"convert: WARN: block {idx}: missing fn ref id={ref_id}",
                file=sys.stderr,
            )
            refs_skipped += 1
            continue
        esc = escape_typst(body_text).replace("\n", " ")
        out_parts.append(f"#fn[{esc}]")
        fn_emitted += 1

    for ref_id in en_refs:
        body_text = en_by_id.get(ref_id)
        if body_text is None:
            print(
                f"convert: WARN: block {idx}: missing en ref id={ref_id}",
                file=sys.stderr,
            )
            refs_skipped += 1
            continue
        esc = escape_typst(body_text).replace("\n", " ")
        out_parts.append(f"#en[{esc}]")
        en_emitted += 1

    return "".join(out_parts), fn_emitted, en_emitted, refs_skipped


# ---------------------------------------------------------------------------
# Driver
# ---------------------------------------------------------------------------
TEMPLATE_PROLOGUE = """\
#import "{template_path}": book, chapter, subtitle, body, ornament, fn, en

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
