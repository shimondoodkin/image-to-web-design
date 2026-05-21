#!/usr/bin/env python3
"""Convert an image to a different format.

Terminal op — does not write a receipt. Default format is webp at quality 98.

Usage: convert.py INPUT [--format webp|png|jpg] [--quality N=98] --out PATH
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from PIL import Image


FORMAT_TO_PIL = {"webp": "WEBP", "png": "PNG", "jpg": "JPEG", "jpeg": "JPEG"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert image format.")
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--format",
        choices=["webp", "png", "jpg", "jpeg"],
        default="webp",
    )
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    pil_fmt = FORMAT_TO_PIL[args.format]
    save_kwargs: dict[str, int] = {}
    if pil_fmt in {"WEBP", "JPEG"}:
        save_kwargs["quality"] = args.quality

    with Image.open(args.input) as img:
        if pil_fmt == "JPEG" and img.mode in {"RGBA", "LA", "P"}:
            img = img.convert("RGB")
        img.save(args.out, format=pil_fmt, **save_kwargs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
