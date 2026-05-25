#!/usr/bin/env python3
"""Pre-scale an image to match OpenAI's vision pipeline exactly.

OpenAI vision (detail:high) processes images in two stages:

  1. Scale to fit within 2048x2048 (downscale only, preserving aspect).
  2. Scale so the shortest side is 768 px (downscale only — small inputs
     pass through unchanged).

The processed image is what the model actually sees. By doing both
stages client-side we send exactly what the model processes — no
internal rescaling, and coordinates round-trip accurately
(validated to under 1.4 px noise in
docs/research/2026-05-12-vision-validation-report.md).

Usage:
  vision_prep.py INPUT [--quality N=98] --out PATH

No --model flag: this script is OpenAI-only. No --color flag: the
OpenAI pipeline does not pad, so no fill colour is needed.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageFilter
from _common import write_receipt, save_image_with_quality  # noqa: E402


def compute_target(in_w: int, in_h: int) -> tuple[float, tuple[int, int]]:
    """Return (scale, (out_w, out_h)) for the OpenAI vision pipeline."""
    s1 = min(1.0, 2048 / max(in_w, in_h))
    short_after_s1 = min(in_w * s1, in_h * s1)
    s2 = 768 / short_after_s1 if short_after_s1 > 768 else 1.0
    scale = s1 * s2
    out_w = max(1, round(in_w * scale))
    out_h = max(1, round(in_h * scale))
    return scale, (out_w, out_h)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-scale an image to match OpenAI's vision pipeline."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    with Image.open(args.input) as img:
        in_w, in_h = img.size
        if img.mode not in {"RGB", "RGBA"}:
            img = img.convert("RGB")

        scale, (out_w, out_h) = compute_target(in_w, in_h)

        if scale < 1.0:
            resized = img.resize((out_w, out_h), Image.Resampling.LANCZOS)
            resized = resized.filter(
                ImageFilter.UnsharpMask(radius=1, percent=80, threshold=0)
            )
        else:
            resized = img

        save_image_with_quality(resized, args.out, args.quality)

    write_receipt(
        out_path=args.out,
        input_path=args.input,
        input_size=(in_w, in_h),
        output_size=(out_w, out_h),
        op={
            "op": "vision_prep",
            "family": "openai",
            "scale": scale,
            "scaled_size": [out_w, out_h],
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
