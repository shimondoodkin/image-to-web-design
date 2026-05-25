#!/usr/bin/env python3
"""Crop an image to a bbox.

Usage: crop.py INPUT --bbox x1,y1,x2,y2 [--quality N=98] --out PATH
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
from _common import write_receipt, save_image_with_quality  # noqa: E402


def parse_bbox(s: str) -> tuple[int, int, int, int]:
    parts = s.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"bbox must be x1,y1,x2,y2 — got: {s!r}"
        )
    try:
        x1, y1, x2, y2 = (int(p) for p in parts)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"bbox values must be integers — got: {s!r}"
        ) from e
    return x1, y1, x2, y2


def main() -> int:
    parser = argparse.ArgumentParser(description="Crop an image to a bbox.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--bbox", type=parse_bbox, required=True)
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    x1, y1, x2, y2 = args.bbox
    if x1 >= x2 or y1 >= y2:
        print(
            f"error: bbox must have x1<x2 and y1<y2 — got {args.bbox}",
            file=sys.stderr,
        )
        return 2
    if x1 < 0 or y1 < 0:
        print(
            f"error: bbox has negative coordinates — got {args.bbox}",
            file=sys.stderr,
        )
        return 2

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    with Image.open(args.input) as img:
        in_w, in_h = img.size
        if x2 > in_w or y2 > in_h:
            print(
                f"error: bbox {args.bbox} exceeds image bounds "
                f"({in_w}x{in_h})",
                file=sys.stderr,
            )
            return 2
        cropped = img.crop((x1, y1, x2, y2))
        save_image_with_quality(cropped, args.out, args.quality)
        out_w, out_h = cropped.size

    write_receipt(
        out_path=args.out,
        input_path=args.input,
        input_size=(in_w, in_h),
        output_size=(out_w, out_h),
        op={"op": "crop", "bbox": [x1, y1, x2, y2]},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
