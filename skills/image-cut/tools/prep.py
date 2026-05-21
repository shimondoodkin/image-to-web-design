#!/usr/bin/env python3
"""High-level: prepare an image (or region of it) for Claude vision.

Composes crop + optional pad + vision_prep in one call. Output is at the
exact size Claude will process (scaled to fit model limits, padded to a
multiple of 28). Source content stays aligned to top-left (origin = (0,0)),
so coordinate translation needs no offset.

Usage:
  prep.py ORIGINAL [--region x1,y1,x2,y2]
                   [--pad-top N --pad-right N --pad-bottom N --pad-left N]
                   [--model sonnet|opus-4.6|opus-4.7|haiku]
                   [--color #000000] [--quality N=98]
                   --out PATH

If --region is omitted, the whole image is used.
Padding (if any) is added AROUND the region BEFORE the vision-prep step.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageFilter
from _common import parse_hex_color, save_image_with_quality  # noqa: E402
from vision_prep import MODEL_LIMITS, compute_target  # noqa: E402


def parse_bbox(s: str) -> tuple[int, int, int, int]:
    parts = s.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"region must be x1,y1,x2,y2 — got: {s!r}"
        )
    try:
        return tuple(int(p) for p in parts)  # type: ignore[return-value]
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"region values must be integers — got: {s!r}"
        ) from e


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Prepare an image region for Claude vision."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--region", type=parse_bbox)
    parser.add_argument("--pad-top", type=int, default=0)
    parser.add_argument("--pad-right", type=int, default=0)
    parser.add_argument("--pad-bottom", type=int, default=0)
    parser.add_argument("--pad-left", type=int, default=0)
    parser.add_argument(
        "--model",
        choices=list(MODEL_LIMITS.keys()),
        default="sonnet",
    )
    parser.add_argument("--color", default="#000000")
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    try:
        color_rgb = parse_hex_color(args.color)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    pads = (args.pad_top, args.pad_right, args.pad_bottom, args.pad_left)
    if any(v < 0 for v in pads):
        print("error: pad values must be non-negative", file=sys.stderr)
        return 2

    with Image.open(args.input) as orig:
        orig_w, orig_h = orig.size

        if args.region:
            x1, y1, x2, y2 = args.region
            if x1 >= x2 or y1 >= y2 or x1 < 0 or y1 < 0:
                print(
                    f"error: invalid region {args.region}", file=sys.stderr
                )
                return 2
            if x2 > orig_w or y2 > orig_h:
                print(
                    f"error: region {args.region} exceeds image bounds "
                    f"({orig_w}x{orig_h})",
                    file=sys.stderr,
                )
                return 2
            img = orig.crop((x1, y1, x2, y2))
        else:
            img = orig.copy()

        if img.mode not in {"RGB", "RGBA"}:
            img = img.convert("RGB")

        pt, pr, pb, pl = pads
        if any(v > 0 for v in pads):
            padded_w = img.width + pl + pr
            padded_h = img.height + pt + pb
            fill = (*color_rgb, 255) if img.mode == "RGBA" else color_rgb
            padded = Image.new(img.mode, (padded_w, padded_h), fill)
            padded.paste(img, (pl, pt))
            img = padded

        scale, (scaled_w, scaled_h), (out_w, out_h) = compute_target(
            img.width, img.height, args.model
        )

        if scale < 1.0:
            resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
            resized = resized.filter(
                ImageFilter.UnsharpMask(radius=1, percent=80, threshold=0)
            )
        else:
            resized = img

        if (out_w, out_h) != (scaled_w, scaled_h):
            fill = (*color_rgb, 255) if resized.mode == "RGBA" else color_rgb
            canvas = Image.new(resized.mode, (out_w, out_h), fill)
            canvas.paste(resized, (0, 0))
            out_img = canvas
        else:
            out_img = resized
        save_image_with_quality(out_img, args.out, args.quality)

    return 0


if __name__ == "__main__":
    sys.exit(main())
