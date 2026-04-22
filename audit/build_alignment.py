#!/usr/bin/env python3
"""
Build audit/alignment.json by finding the best reference-scan match for each
generated page.

The pipeline produces `build/book.pdf` with N pages (currently 15 after M1).
`reference_scans/` contains 20 scans (page_105.png .. page_124.png). The
mapping between generated and reference pages is NOT 1:1 — the typesetter's
line-breaking and apparatus packing cause different page boundaries than the
hand-set printed edition.

This script computes a composite similarity score (SSIM-like approximation +
header-strip Pearson + pHash distance) for every (generated, reference) pair,
picks the best reference per generated page (greedy; allowing
many-to-one mapping since the generator packs more content per page), and
writes the resulting mapping to `audit/alignment.json` in the schema:

    {
      "generated_page_count": 15,
      "reference_scan_count": 20,
      "alignment": {
        "1": "page_105.png",
        "2": "page_106.png",
        ...
      }
    }

If no reference page is sufficiently similar to a generated page, the value
is set to `null` (the generated page won't be scored in image_diff).

Re-run this script whenever the pipeline's page count changes:

    ssh sefer-design "cd repo && rm -rf build && python3 python/convert.py \\
        && ~/.local/bin/typst compile ... \\
        && python3 audit/build_alignment.py"

Then commit the updated `audit/alignment.json`.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path


def _try_import(name):
    try:
        return __import__(name)
    except ImportError:
        return None


PIL = _try_import("PIL")


def phash(image, size: int = 8) -> int:
    from PIL import Image
    im = image.convert("L").resize((size, size), Image.LANCZOS)
    px = list(im.getdata())
    avg = sum(px) / len(px)
    bits = 0
    for i, v in enumerate(px):
        if v >= avg:
            bits |= 1 << i
    return bits


def hamming(a: int, b: int) -> int:
    return bin(a ^ b).count("1")


def ssim(im1, im2) -> float:
    from PIL import Image, ImageStat
    w, h = 256, 362
    a = im1.convert("L").resize((w, h), Image.LANCZOS)
    b = im2.convert("L").resize((w, h), Image.LANCZOS)
    sa = ImageStat.Stat(a)
    sb = ImageStat.Stat(b)
    mu_a, mu_b = sa.mean[0], sb.mean[0]
    var_a, var_b = sa.stddev[0] ** 2, sb.stddev[0] ** 2
    pa = list(a.getdata())
    pb = list(b.getdata())
    n = len(pa)
    mean_prod = sum((xa - mu_a) * (xb - mu_b) for xa, xb in zip(pa, pb)) / n
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    numer = (2 * mu_a * mu_b + c1) * (2 * mean_prod + c2)
    denom = (mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2)
    return max(0.0, min(1.0, numer / denom))


def header_strip_match(im1, im2) -> float:
    from PIL import Image
    import statistics
    w = 256
    a = im1.convert("L").resize((w, im1.height), Image.LANCZOS).crop((0, 0, w, 35))
    b = im2.convert("L").resize((w, im2.height), Image.LANCZOS).crop((0, 0, w, 35))
    pa = list(a.getdata())
    pb = list(b.getdata())
    ta = statistics.mean(pa)
    tb = statistics.mean(pb)
    ba = [1 if p < ta else 0 for p in pa]
    bb = [1 if p < tb else 0 for p in pb]
    agree = sum(1 for x, y in zip(ba, bb) if x == y)
    return agree / len(ba)


def composite_score(im_gen, im_ref) -> float:
    """Same weighted formula as PageReport.score(), without the
    notes_header_found heuristic (which is a single-image property,
    not a pair-property)."""
    s = ssim(im_gen, im_ref)
    p = hamming(phash(im_gen), phash(im_ref))
    h = header_strip_match(im_gen, im_ref)
    phash_pct = max(0.0, 1 - p / 64.0)
    # Weights excluding notes_header_found (renormalised to 80%): 50/20/10 → 62.5/25/12.5
    return 0.625 * s + 0.25 * h + 0.125 * phash_pct


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--gen-dir", type=Path, default=Path("build"))
    ap.add_argument("--reference", type=Path, default=Path("reference_scans"))
    ap.add_argument("--output", type=Path, default=Path("audit/alignment.json"))
    ap.add_argument("--threshold", type=float, default=0.0,
                    help="Composite similarity below which the generated page "
                         "is mapped to null (no reference). 0.0 disables.")
    ap.add_argument("--verbose", action="store_true")
    args = ap.parse_args()

    if PIL is None:
        print("Pillow not installed.", file=sys.stderr)
        return 2

    from PIL import Image

    gen_pages = sorted(args.gen_dir.glob("page-*.png"))
    ref_pages = sorted(args.reference.glob("page_*.png"))
    if not gen_pages:
        print(f"no generated pages under {args.gen_dir}", file=sys.stderr)
        return 1
    if not ref_pages:
        print(f"no reference pages under {args.reference}", file=sys.stderr)
        return 1

    print(f"generated pages: {len(gen_pages)}")
    print(f"reference pages: {len(ref_pages)}")

    # Preload reference images once.
    ref_imgs = [(p, Image.open(p)) for p in ref_pages]

    alignment: dict[str, str | None] = {}
    rows = []
    for idx, gen_path in enumerate(gen_pages, start=1):
        gen_im = Image.open(gen_path)
        best_score = -1.0
        best_name: str | None = None
        per_ref = []
        for ref_path, ref_im in ref_imgs:
            s = composite_score(gen_im, ref_im)
            per_ref.append((ref_path.name, s))
            if s > best_score:
                best_score = s
                best_name = ref_path.name
        if best_score < args.threshold:
            best_name = None
        alignment[str(idx)] = best_name
        rows.append((idx, gen_path.name, best_name, best_score, per_ref))
        if args.verbose:
            top3 = sorted(per_ref, key=lambda r: -r[1])[:3]
            top3_fmt = ", ".join(f"{n}={s:.3f}" for n, s in top3)
            print(f"  gen {idx:2d} → {best_name} (score={best_score:.3f}) [{top3_fmt}]")

    out = {
        "generated_page_count": len(gen_pages),
        "reference_scan_count": len(ref_pages),
        "description": (
            "Semantic mapping from generated page index (1..N) to the "
            "reference_scans/*.png that best matches it. null = no suitable "
            "reference. Built by audit/build_alignment.py; commit this file "
            "whenever the pipeline's page count changes."
        ),
        "alignment": alignment,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(out, indent=2) + "\n", encoding="utf-8")
    print(f"wrote {args.output}")

    print("\nSummary:")
    for idx, gen, ref, sc, _ in rows:
        print(f"  {idx:2d}  {gen} → {ref or '(null)':16s}  score={sc:.3f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
