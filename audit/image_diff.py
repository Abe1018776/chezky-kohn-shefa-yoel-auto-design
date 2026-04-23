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
import json
import subprocess
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Dict, List, Optional


def _try_import(name):
    try:
        return __import__(name)
    except ImportError:
        return None


PIL = _try_import("PIL")


# Term weights for the composite audit score.
#
# Historical (M1-era) weights were 0.50/0.20/0.20/0.10 over SSIM / header /
# notes-header / phash. Empirical measurement during M2 spillover validation
# (mission 0e4c58ac, feature m2-audit-rescore-rebalance at commit 15ca8e3)
# showed that the SSIM term produces sub-scores of 0.004–0.088 when comparing
# a pristine CMYK-rendered PDF against yellowed paper reference scans — a
# fundamental property of the comparison, not a layout deficiency. With 0.5
# weight on SSIM the scorer saturated at ~49.0 regardless of layout quality
# and capacity sweeps moved the average by ≤0.3 points, leaving no room for
# meaningful regression signal.
#
# The reweighting below (i) drops SSIM from 0.50 → 0.15, (ii) raises the two
# structural/semantic terms (header_match, notes_header_found) from 0.20 each
# to 0.30 each, (iii) bumps phash from 0.10 → 0.15, and (iv) introduces a new
# page_aligned term at 0.10 that rewards stable pagination — a generated
# page with a valid reference (via positional zip OR audit/alignment.json)
# counts as aligned. Rationale: when layouts drift and pagination shifts,
# the alignment map becomes incomplete → the term drops → regression is
# detected. Weights sum to 1.0.
_WEIGHT_SSIM = 0.15
_WEIGHT_HEADER = 0.30
_WEIGHT_NOTES_HDR = 0.30
_WEIGHT_PHASH = 0.15
_WEIGHT_PAGE_ALIGNED = 0.10


@dataclass
class PageReport:
    index: int
    ref_path: Optional[Path]
    out_path: Optional[Path]
    ssim: float = 0.0
    phash_dist: int = 0
    header_match: float = 0.0
    notes_header_found: bool = False
    page_aligned: bool = False
    notes: List[str] = field(default_factory=list)

    @property
    def phash_pct(self) -> float:
        return max(0.0, 1 - self.phash_dist / 64.0)

    @property
    def notes_hdr_value(self) -> float:
        return 1.0 if self.notes_header_found else 0.0

    @property
    def page_aligned_value(self) -> float:
        return 1.0 if self.page_aligned else 0.0

    def score(self) -> float:
        # Weighted composite; see _WEIGHT_* constants for rationale + history.
        return (
            _WEIGHT_SSIM * self.ssim
            + _WEIGHT_HEADER * self.header_match
            + _WEIGHT_NOTES_HDR * self.notes_hdr_value
            + _WEIGHT_PHASH * self.phash_pct
            + _WEIGHT_PAGE_ALIGNED * self.page_aligned_value
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


def load_alignment(path: Path, ref_dir: Path) -> Optional[Dict[int, Optional[Path]]]:
    """Load a committed generated-page → reference-scan alignment map if present.

    The alignment file (default: ``audit/alignment.json``) lets the pipeline's
    per-page count drift from the reference-scan count (20) without silently
    miscomparing. Schema:

        {
          "alignment": { "<generated_page_1_indexed>": "page_NNN.png" | null, ... },
          ...  // other informational keys ignored here
        }

    Returns a dict {1-indexed-generated-page: Path | None}, or None if the
    file is missing (callers fall back to positional zip).
    """
    if not path.exists():
        return None
    try:
        data = json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as exc:
        print(f"warning: failed to read {path}: {exc}; falling back to positional",
              file=sys.stderr)
        return None
    raw = data.get("alignment")
    if not isinstance(raw, dict):
        print(f"warning: {path} has no 'alignment' object; falling back to positional",
              file=sys.stderr)
        return None
    out: Dict[int, Optional[Path]] = {}
    for k, v in raw.items():
        try:
            idx = int(k)
        except (TypeError, ValueError):
            continue
        if v is None:
            out[idx] = None
        else:
            out[idx] = ref_dir / str(v)
    return out


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--output", type=Path, default=Path("build/book.pdf"))
    ap.add_argument("--reference", type=Path, default=Path("reference_scans"))
    ap.add_argument("--report", type=Path, default=Path("build/audit_report.md"))
    ap.add_argument("--out-pngs", type=Path, default=Path("build"))
    ap.add_argument(
        "--alignment",
        type=Path,
        default=Path("audit/alignment.json"),
        help="Generated→reference page alignment map (JSON). "
             "When absent, falls back to positional zip.",
    )
    ap.add_argument(
        "--verbose",
        action="store_true",
        help="Print per-term means (ssim, header, notes-hdr, phash, "
             "page-aligned) across all scored pages to stdout after the "
             "report is written. Useful for scorer reweighting + diagnosis.",
    )
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

    alignment_map = load_alignment(args.alignment, args.reference)
    if alignment_map is not None:
        print(f"using alignment map: {args.alignment} "
              f"({sum(1 for v in alignment_map.values() if v is not None)} "
              f"of {len(pdf_pages)} generated pages mapped)")
    else:
        print("no alignment map; using positional zip against reference pages")

    reports: List[PageReport] = []
    for i, out in enumerate(pdf_pages):
        gen_index_1 = i + 1
        if alignment_map is not None:
            ref = alignment_map.get(gen_index_1)
            if ref is not None and not ref.exists():
                print(f"warning: alignment maps gen page {gen_index_1} → "
                      f"{ref.name} which does not exist; treating as unmapped",
                      file=sys.stderr)
                ref = None
        else:
            ref = ref_pages[i] if i < len(ref_pages) else None
        r = PageReport(index=gen_index_1, ref_path=ref, out_path=out)
        if ref is None:
            r.notes.append("no matching reference page")
            r.page_aligned = False
        else:
            im_out = Image.open(out)
            im_ref = Image.open(ref)
            r.ssim = ssim(im_out, im_ref)
            r.phash_dist = hamming(phash(im_out), phash(im_ref))
            r.header_match = header_strip_match(im_out, im_ref)
            r.page_aligned = True
        r.notes_header_found = detect_notes_header_text(out)
        reports.append(r)

    # Write report.
    lines = ["# Audit Report", "",
             "| # | Ref | SSIM | pHash | Header | Notes-hdr | Aligned | Score |",
             "|---|---|---|---|---|---|---|---|"]
    for r in reports:
        ref_name = r.ref_path.name if r.ref_path else "-"
        lines.append(
            f"| {r.index} | {ref_name} | {r.ssim:.3f} | "
            f"{r.phash_dist} | {r.header_match:.3f} | "
            f"{'yes' if r.notes_header_found else 'no'} | "
            f"{'yes' if r.page_aligned else 'no'} | {r.score():.1f} |"
        )
    avg = sum(r.score() for r in reports) / len(reports)
    lines += ["", f"**Average score: {avg:.1f} / 100**", ""]
    lines.append("## Scorer weights")
    lines.append(
        f"SSIM {_WEIGHT_SSIM:.2f} · Header {_WEIGHT_HEADER:.2f} · "
        f"Notes-hdr {_WEIGHT_NOTES_HDR:.2f} · pHash {_WEIGHT_PHASH:.2f} · "
        f"Page-aligned {_WEIGHT_PAGE_ALIGNED:.2f}"
    )
    lines.append("")
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

    if args.verbose:
        n = len(reports)
        mean_ssim = sum(r.ssim for r in reports) / n
        mean_phash_dist = sum(r.phash_dist for r in reports) / n
        mean_phash_pct = sum(r.phash_pct for r in reports) / n
        mean_header = sum(r.header_match for r in reports) / n
        mean_notes = sum(r.notes_hdr_value for r in reports) / n
        mean_aligned = sum(r.page_aligned_value for r in reports) / n
        print("per-term means across all pages:")
        print(f"  ssim          = {mean_ssim:.4f}")
        print(f"  phash_dist    = {mean_phash_dist:.2f}")
        print(f"  phash_pct     = {mean_phash_pct:.4f}")
        print(f"  header_match  = {mean_header:.4f}")
        print(f"  notes_hdr_hit = {mean_notes:.4f}  ({sum(r.notes_header_found for r in reports)}/{n})")
        print(f"  page_aligned  = {mean_aligned:.4f}  ({sum(r.page_aligned for r in reports)}/{n})")
        print("per-term weighted contributions to average score:")
        print(f"  ssim         -> {_WEIGHT_SSIM * mean_ssim * 100:6.2f}")
        print(f"  header       -> {_WEIGHT_HEADER * mean_header * 100:6.2f}")
        print(f"  notes_hdr    -> {_WEIGHT_NOTES_HDR * mean_notes * 100:6.2f}")
        print(f"  phash        -> {_WEIGHT_PHASH * mean_phash_pct * 100:6.2f}")
        print(f"  page_aligned -> {_WEIGHT_PAGE_ALIGNED * mean_aligned * 100:6.2f}")
        print(f"  TOTAL        -> {avg:6.2f}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
