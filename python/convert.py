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

# A call-out in the body text looks like `[א]` (Hebrew letter in brackets).
# We pull those out BEFORE escaping, so we can replace them with `#fn[...]` /
# `#en[...]` calls in the correct order.
CALLOUT_RE = re.compile(r"\[([\u05D0-\u05EA]{1,3})\]")


def escape_typst(s: str) -> str:
    # Preserve Hebrew and niqqud as-is; escape only Typst syntax chars.
    return "".join(_TYPST_SPECIALS.get(c, c) for c in s)


# ---------------------------------------------------------------------------
# Body rendering: inline call-outs -> #fn[] / #en[] in source order
# ---------------------------------------------------------------------------
def render_body(block: dict) -> str:
    """Convert a body block's text into Typst source with #fn[]/#en[] calls.

    Footnote / endnote call-outs in the JSON body text are bracketed Hebrew
    letters like `[א]`. The pagination-study spec (§1.1) says to pair them
    with `footnotes[i]` / `endnotes[i]` **positionally**, not by numeric id.
    Here we walk the body left-to-right and pop from each queue in turn.
    """
    text = block["text"]
    fn_queue: List[dict] = list(block.get("footnotes") or [])
    en_queue: List[dict] = list(block.get("endnotes") or [])
    fn_ref_ids = list(block.get("footnote_refs") or [])
    en_ref_ids = list(block.get("endnote_refs") or [])

    # Map id -> body text (fast lookup), for cases where the id ordering in
    # footnote_refs doesn't match the positional queue (rare but possible).
    fn_by_id = {str(f["id"]): f["text"] for f in fn_queue}
    en_by_id = {str(e["id"]): e["text"] for e in en_queue}

    # Build a merged list of (start, end, kind, note_body) call-outs.
    # Strategy: find every [Hebrew-letter] token. Each token consumes the next
    # available note from fn_queue (the footnote apparatus is more common and
    # always appears before endnotes in JSON order). If fn_queue is empty but
    # en_queue isn't, it's an endnote call-out.
    calls: List[tuple] = []
    fn_used = 0
    en_used = 0
    for m in CALLOUT_RE.finditer(text):
        if fn_used < len(fn_queue):
            note = fn_queue[fn_used]["text"]
            calls.append((m.start(), m.end(), "fn", note))
            fn_used += 1
        elif en_used < len(en_queue):
            note = en_queue[en_used]["text"]
            calls.append((m.start(), m.end(), "en", note))
            en_used += 1
        else:
            calls.append((m.start(), m.end(), "fn", ""))  # orphan marker

    # If there are residual endnotes without an inline bracket, append them
    # at paragraph end so they still pin to this page.
    trailing_en: List[str] = []
    if en_used < len(en_queue):
        for e in en_queue[en_used:]:
            trailing_en.append(e["text"])

    # Stitch the Typst source.
    out_parts: List[str] = []
    cursor = 0
    for (start, end, kind, note) in calls:
        out_parts.append(escape_typst(text[cursor:start]))
        esc = escape_typst(note).replace("\n", " ")
        if kind == "fn":
            out_parts.append(f"#fn[{esc}]")
        else:
            out_parts.append(f"#en[{esc}]")
        cursor = end
    out_parts.append(escape_typst(text[cursor:]))
    for note in trailing_en:
        esc = escape_typst(note).replace("\n", " ")
        out_parts.append(f"#en[{esc}]")

    return "".join(out_parts)


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
) -> str:
    blocks = data["docx_content"]

    out: List[str] = [
        TEMPLATE_PROLOGUE.format(
            template_path=template_path,
            shaar=shaar,
            start_folio=start_folio,
        )
    ]

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
        rendered = render_body(block)
        out.append("#body[\n")
        out.append(rendered)
        out.append("\n]\n\n")

    if pending_chapter is not None:
        out.append(f'#chapter("{escape_typst(pending_chapter)}", "")\n')

    return "".join(out)


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

    src = convert(
        data,
        template_path=rel_tpl_for_out.replace("\\", "/"),
        shaar=args.shaar,
        start_folio=args.start_folio,
    )
    out.write_text(src, encoding="utf-8")
    print(f"wrote {out}  ({len(src)} chars)")


if __name__ == "__main__":
    main()
