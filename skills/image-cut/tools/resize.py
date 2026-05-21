#!/usr/bin/env python3
"""Resize an image.

Modes (mutually exclusive):
  --fit-width N         scale so width = N, height proportional
  --fit-height N        scale so height = N, width proportional
  --width N --height N  both required, explicit size, may distort
  --scale F             multiply both dims by F
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
from _common import write_receipt, save_image_with_quality  # noqa: E402


def main() -> int:
    parser = argparse.ArgumentParser(description="Resize an image.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--fit-width", type=int)
    parser.add_argument("--fit-height", type=int)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--scale", type=float)
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    explicit_mode = args.width is not None or args.height is not None
    if explicit_mode and (args.width is None or args.height is None):
        print(
            "error: --width and --height must be used together",
            file=sys.stderr,
        )
        return 2
    modes_set = sum([
        args.fit_width is not None,
        args.fit_height is not None,
        explicit_mode,
        args.scale is not None,
    ])
    if modes_set == 0:
        print(
            "error: must specify one of --fit-width / --fit-height / "
            "(--width and --height) / --scale",
            file=sys.stderr,
        )
        return 2
    if modes_set > 1:
        print("error: resize modes are mutually exclusive", file=sys.stderr)
        return 2

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    with Image.open(args.input) as img:
        in_w, in_h = img.size
        if args.fit_width is not None:
            mode = "fit-width"
            out_w = args.fit_width
            out_h = max(1, round(in_h * out_w / in_w))
        elif args.fit_height is not None:
            mode = "fit-height"
            out_h = args.fit_height
            out_w = max(1, round(in_w * out_h / in_h))
        elif explicit_mode:
            mode = "explicit"
            out_w, out_h = args.width, args.height
        else:
            mode = "scale"
            out_w = max(1, round(in_w * args.scale))
            out_h = max(1, round(in_h * args.scale))

        if out_w <= 0 or out_h <= 0:
            print(
                f"error: resize produced non-positive size ({out_w}x{out_h})",
                file=sys.stderr,
            )
            return 2

        resized = img.resize((out_w, out_h), Image.Resampling.LANCZOS)
        save_image_with_quality(resized, args.out, args.quality)

    write_receipt(
        out_path=args.out,
        input_path=args.input,
        input_size=(in_w, in_h),
        output_size=(out_w, out_h),
        op={
            "op": "resize",
            "mode": mode,
            "in_size": [in_w, in_h],
            "out_size": [out_w, out_h],
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
