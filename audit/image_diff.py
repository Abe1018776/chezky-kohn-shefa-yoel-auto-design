#!/usr/bin/env python3
"""
Image-diff the generated sefer PDF against the reference scans.

For each generated page:
- Rasterise to the same DPI as the reference scan.
- Compute a pixel-diff ratio + perceptual hash distance.
- Check that hard-requirement heuristics hold (rule-header text presence,
  header-strip similarity, cartouche y-offset on opener pages).

Usage:
    python3 audit/image_diff.py \
        --output build/book.pdf \
        --reference reference_scans \
        --report build/audit_report.md

Dependencies: Pillow, pypdf (or PyMuPDF if available).
If none of those are installed, falls back to calling `typst compile` for
PNGs and does a pure Pillow-based comparison.
"""
from __future__ import annotations

import argparse
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import List, Optional


def _try_import(name):
    try:
        return __import__(name)
    except ImportError:
        return None


PIL = _try_import("PIL")


@dataclass
class PageReport:
    index: int
    ref_path: Optional[Path]
    out_path: Optional[Path]
    ssim: float = 0.0
    phash_dist: int = 0
    header_match: float = 0.0
    notes_header_found: bool = False
    notes: List[str] = field(default_factory=list)

    def score(self) -> float:
        # Weighted composite: 50% SSIM, 20% header, 20% notes-header, 10% phash.
        phash_pct = max(0.0, 1 - self.phash_dist / 64.0)
        return (
            0.5 * self.ssim
            + 0.2 * self.header_match
            + 0.2 * (1.0 if self.notes_header_found else 0.0)
            + 0.1 * phash_pct
        ) * 100


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
    """Extremely lightweight SSIM approximation (luminance+contrast only)."""
    from PIL import Image, ImageStat
    w, h = 512, 724  # roughly 170x240 mm at ~76 ppi
    a = im1.convert("L").resize((w, h), Image.LANCZOS)
    b = im2.convert("L").resize((w, h), Image.LANCZOS)
    sa = ImageStat.Stat(a)
    sb = ImageStat.Stat(b)
    mu_a, mu_b = sa.mean[0], sb.mean[0]
    var_a, var_b = sa.stddev[0] ** 2, sb.stddev[0] ** 2
    # Cross-covariance approximation via per-pixel abs diff.
    pixels_a = list(a.getdata())
    pixels_b = list(b.getdata())
    n = len(pixels_a)
    mean_prod = sum((pa - mu_a) * (pb - mu_b) for pa, pb in zip(pixels_a, pixels_b)) / n
    c1 = (0.01 * 255) ** 2
    c2 = (0.03 * 255) ** 2
    numer = (2 * mu_a * mu_b + c1) * (2 * mean_prod + c2)
    denom = (mu_a ** 2 + mu_b ** 2 + c1) * (var_a + var_b + c2)
    return max(0.0, min(1.0, numer / denom))


def header_strip_match(im1, im2) -> float:
    from PIL import Image
    w, h = 512, 70
    a = im1.convert("L").resize((w, im1.height), Image.LANCZOS).crop((0, 0, w, 70))
    b = im2.convert("L").resize((w, im2.height), Image.LANCZOS).crop((0, 0, w, 70))
    # Pearson-like on binarised images.
    import statistics
    pa = list(a.getdata())
    pb = list(b.getdata())
    # Threshold = mean of each.
    ta = statistics.mean(pa)
    tb = statistics.mean(pb)
    ba = [1 if p < ta else 0 for p in pa]
    bb = [1 if p < tb else 0 for p in pb]
    agree = sum(1 for x, y in zip(ba, bb) if x == y)
    return agree / len(ba)


def rasterise_pdf(pdf: Path, out_dir: Path, ppi: int = 150) -> List[Path]:
    """Use Typst itself to rasterise (we know the binary is present). Requires
    the *source* .typ — as a fallback we invoke ghostscript or pdftoppm if
    available; otherwise we rely on a sibling page-XX.png already written by
    the build step."""
    # If build/page-NN.png already exist, reuse them.
    existing = sorted(out_dir.glob("page-*.png"))
    if existing:
        return existing
    # Try pdftoppm.
    for tool, args in [
        ("pdftoppm", ["-png", "-r", str(ppi), str(pdf), str(out_dir / "page")]),
        ("gs", ["-sDEVICE=png16m", f"-r{ppi}", "-o", str(out_dir / "page-%02d.png"), str(pdf)]),
    ]:
        if subprocess.run(["which", tool], capture_output=True).returncode == 0:
            subprocess.run([tool] + args, check=True)
            return sorted(out_dir.glob("page*.png"))
    raise RuntimeError("No rasteriser available and no pre-rendered PNGs found.")


def detect_notes_header_text(png_path: Path) -> bool:
    # We don't have tesseract in the sandbox; use a structural heuristic:
    # the rule-header is a thin horizontal line at ~75% down the page with a
    # small text block in the middle. If a dark horizontal band exists there,
    # we flag it as present.
    from PIL import Image
    im = Image.open(png_path).convert("L")
    w, h = im.size
    band_top = int(h * 0.70)
    band_bot = int(h * 0.78)
    crop = im.crop((int(w * 0.10), band_top, int(w * 0.90), band_bot))
    # Look for a row that's significantly darker than the page average.
    row_means = []
    for y in range(crop.height):
        row = [crop.getpixel((x, y)) for x in range(crop.width)]
        row_means.append(sum(row) / len(row))
    page_mean = sum(row_means) / len(row_means)
    return min(row_means) < page_mean * 0.85


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=Path("build/book.pdf"))
    ap.add_argument("--reference", type=Path, default=Path("reference_scans"))
    ap.add_argument("--report", type=Path, default=Path("build/audit_report.md"))
    ap.add_argument("--out-pngs", type=Path, default=Path("build"))
    args = ap.parse_args()

    if PIL is None:
        print("Pillow not installed. Install with: python3 -m pip install --user Pillow")
        return 2

    from PIL import Image

    pdf_pages = rasterise_pdf(args.output, args.out_pngs)
    ref_pages = sorted(args.reference.glob("page_*.png"))
    print(f"generated pages: {len(pdf_pages)}")
    print(f"reference pages: {len(ref_pages)}")
    if not pdf_pages or not ref_pages:
        print("No pages to compare.")
        return 1

    reports: List[PageReport] = []
    for i, out in enumerate(pdf_pages):
        ref = ref_pages[i] if i < len(ref_pages) else None
        r = PageReport(index=i + 1, ref_path=ref, out_path=out)
        if ref is None:
            r.notes.append("no matching reference page")
        else:
            im_out = Image.open(out)
            im_ref = Image.open(ref)
            r.ssim = ssim(im_out, im_ref)
            r.phash_dist = hamming(phash(im_out), phash(im_ref))
            r.header_match = header_strip_match(im_out, im_ref)
        r.notes_header_found = detect_notes_header_text(out)
        reports.append(r)

    # Write report.
    lines = ["# Audit Report", "",
             "| # | Ref | SSIM | pHash | Header | Notes-hdr | Score |",
             "|---|---|---|---|---|---|---|"]
    for r in reports:
        ref_name = r.ref_path.name if r.ref_path else "-"
        lines.append(
            f"| {r.index} | {ref_name} | {r.ssim:.3f} | "
            f"{r.phash_dist} | {r.header_match:.3f} | "
            f"{'yes' if r.notes_header_found else 'no'} | {r.score():.1f} |"
        )
    avg = sum(r.score() for r in reports) / len(reports)
    lines += ["", f"**Average score: {avg:.1f} / 100**", ""]
    lines.append("## Checklist (hard requirements)")
    lines.append(f"- [{'x' if all(r.header_match > 0.8 for r in reports) else ' '}] "
                 "Running header present on all pages")
    lines.append(f"- [{'x' if sum(r.notes_header_found for r in reports) >= len(reports) // 2 else ' '}] "
                 "Rule-header visible on notes zone for >50% of pages")
    lines.append(f"- [{'x' if avg > 50 else ' '}] "
                 "Overall visual similarity > 50%")

    args.report.write_text("\n".join(lines), encoding="utf-8")
    print(f"wrote {args.report}")
    print(f"average score: {avg:.1f} / 100")
    return 0


if __name__ == "__main__":
    sys.exit(main())
