#!/usr/bin/env python3
"""High-level: translate points looked-at in a prep'd image → original coords.

Re-derives the same crop + pad + vision_prep transform that prep.py applied,
then translates each input point back to the original image's pixel space.
Stateless — pass the same ORIGINAL + --region + padding + --model flags you
passed to prep.py.

Usage:
  points.py ORIGINAL [--region x1,y1,x2,y2]
                     [--pad-top N --pad-right N --pad-bottom N --pad-left N]
                     [--model sonnet|opus-4.6|opus-4.7|haiku]
                     --points "px,py;px,py;..."
                     [--round]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
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


def parse_points(s: str) -> list[tuple[float, float]]:
    out = []
    for chunk in s.split(";"):
        chunk = chunk.strip()
        if not chunk:
            continue
        parts = chunk.split(",")
        if len(parts) != 2:
            raise argparse.ArgumentTypeError(
                f"each point must be x,y — got: {chunk!r}"
            )
        try:
            out.append((float(parts[0]), float(parts[1])))
        except ValueError as e:
            raise argparse.ArgumentTypeError(
                f"point values must be numbers — got: {chunk!r}"
            ) from e
    if not out:
        raise argparse.ArgumentTypeError("--points requires at least one point")
    return out


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Translate prep-view points back to original coords."
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
    parser.add_argument("--points", type=parse_points, required=True)
    parser.add_argument("--round", action="store_true")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
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
            print(f"error: invalid region {args.region}", file=sys.stderr)
            return 2
        if x2 > orig_w or y2 > orig_h:
            print(
                f"error: region exceeds image bounds ({orig_w}x{orig_h})",
                file=sys.stderr,
            )
            return 2
        crop_w, crop_h = x2 - x1, y2 - y1
        crop_x1, crop_y1 = x1, y1
    else:
        crop_w, crop_h = orig_w, orig_h
        crop_x1, crop_y1 = 0, 0

    pt, pr, pb, pl = pads
    padded_w = crop_w + pl + pr
    padded_h = crop_h + pt + pb

    scale, _scaled_size, _padded_size = compute_target(
        padded_w, padded_h, args.model
    )

    # prep coord px,py → original coord:
    #   1. undo vision_prep scale: prep_xy / scale = padded_xy
    #   2. undo padding offset:     padded_xy - (pl, pt) = crop_xy
    #   3. undo crop offset:        crop_xy + (crop_x1, crop_y1) = orig_xy
    out_points = []
    for (px, py) in args.points:
        padded_x = px / scale
        padded_y = py / scale
        crop_x = padded_x - pl
        crop_y = padded_y - pt
        orig_x = crop_x + crop_x1
        orig_y = crop_y + crop_y1
        if args.round:
            out_points.append([int(round(orig_x)), int(round(orig_y))])
        else:
            out_points.append([orig_x, orig_y])

    print(json.dumps({"points": out_points}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
