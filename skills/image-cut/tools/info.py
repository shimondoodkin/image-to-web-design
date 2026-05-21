#!/usr/bin/env python3
"""Print metadata about an image, including a vision_safe check.

Usage: info.py INPUT
"""
from __future__ import annotations
import argparse
import json
import sys
from math import gcd
from pathlib import Path
from PIL import Image


def aspect_ratio(w: int, h: int) -> str:
    g = gcd(w, h)
    return f"{w // g}:{h // g}"


def is_vision_safe(w: int, h: int) -> bool:
    """True when long edge <=1568 AND width >= height (landscape or square)."""
    return max(w, h) <= 1568 and w >= h


def main() -> int:
    parser = argparse.ArgumentParser(description="Print image metadata as JSON.")
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2
    with Image.open(args.input) as img:
        w, h = img.size
        info = {
            "path": str(args.input),
            "width": w,
            "height": h,
            "aspect": aspect_ratio(w, h),
            "format": img.format,
            "mode": img.mode,
            "size_bytes": args.input.stat().st_size,
            "vision_safe": is_vision_safe(w, h),
        }
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
