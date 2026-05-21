#!/usr/bin/env python3
"""Add per-side margins to an image.

Usage: pad.py INPUT [--pad-top N] [--pad-right N] [--pad-bottom N]
                    [--pad-left N] [--color #000000] [--quality N=98]
                    --out PATH
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
from _common import write_receipt, parse_hex_color, save_image_with_quality  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Add per-side margins to an image.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--pad-top", type=int, default=0)
    parser.add_argument("--pad-right", type=int, default=0)
    parser.add_argument("--pad-bottom", type=int, default=0)
    parser.add_argument("--pad-left", type=int, default=0)
    parser.add_argument("--color", default="#000000")
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    pads = {
        "top": args.pad_top,
        "right": args.pad_right,
        "bottom": args.pad_bottom,
        "left": args.pad_left,
    }
    if all(v == 0 for v in pads.values()):
        print(
            "error: at least one of --pad-top/--pad-right/--pad-bottom/"
            "--pad-left must be > 0",
            file=sys.stderr,
        )
        return 2
    if any(v < 0 for v in pads.values()):
        print("error: pad values must be non-negative", file=sys.stderr)
        return 2

    try:
        color_rgb = parse_hex_color(args.color)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    with Image.open(args.input) as img:
        in_w, in_h = img.size
        new_w = in_w + pads["left"] + pads["right"]
        new_h = in_h + pads["top"] + pads["bottom"]
        if img.mode == "RGBA":
            fill = (*color_rgb, 255)
        else:
            fill = color_rgb
            if img.mode != "RGB":
                img = img.convert("RGB")
        padded = Image.new(img.mode, (new_w, new_h), fill)
        padded.paste(img, (pads["left"], pads["top"]))
        save_image_with_quality(padded, args.out, args.quality)

    color_hex = "#{:02x}{:02x}{:02x}".format(*color_rgb)
    write_receipt(
        out_path=args.out,
        input_path=args.input,
        input_size=(in_w, in_h),
        output_size=(new_w, new_h),
        op={"op": "pad", "pad": pads, "color": color_hex},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
