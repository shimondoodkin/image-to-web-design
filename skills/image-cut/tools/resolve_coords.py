#!/usr/bin/env python3
"""Resolve coordinates from a prep_claude.py emitted image back to the original.

prep_claude.py downscales content by `scale` and pastes it at (0,0), so the
inverse is just: original = detected / scale (clamped to the original bounds).
This tool applies that to a FLEXIBLE coordinate structure and preserves its
shape — so you can hand it whatever the model gave you:

  - a point            [x, y]
  - a box              [x1, y1, x2, y2]
  - a polygon          [x1, y1, x2, y2, x3, y3, ...]   (any even-length list)
  - a point dict       {"x": .., "y": ..}              (extra keys preserved)
  - named entities     {"logo": [40,30], "cta": [700,520,760,560]}
  - arrays / groups    [[x,y], [x,y], ...] or nested mixes of all the above

Any even-length list of numbers is treated as flattened (x,y) pairs; dicts with
"x"/"y" are treated as points; everything else is walked recursively and copied
through unchanged.

The transform is taken from (in order):
  1. the receipt written next to the emitted image (<output>.json) — exact;
  2. else the original image's size + the baked 768 target (matches prep_claude).

Coordinates come from --coords (inline JSON), -f FILE, or stdin; the resolved
structure is printed as JSON (and written to --out-json if given).

Examples:
  resolve_coords.py --output prepped.png --coords '[384, 540]'
  resolve_coords.py --output prepped.png --coords '{"logo":[40,30],"cta":[700,520,760,560]}'
  resolve_coords.py --input orig.png -f detections.json
  echo '[[100,100],[700,500]]' | resolve_coords.py --output prepped.png
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image

TARGET_EDGE = 768  # must match prep_claude.py


def load_transform(args) -> tuple[float, int, int, str]:
    """Return (scale, orig_w, orig_h, source)."""
    receipt = None
    if args.receipt:
        receipt = Path(args.receipt)
    elif args.output:
        cand = Path(str(args.output) + ".json")
        if cand.exists():
            receipt = cand
    if receipt and receipt.exists():
        r = json.loads(receipt.read_text())
        scale = float(r["op"]["scale"])
        w, h = r["input"]["size"]
        return scale, int(w), int(h), f"receipt:{receipt.name}"
    if args.input:
        with Image.open(args.input) as im:
            w, h = im.size
        return min(1.0, TARGET_EDGE / max(w, h)), w, h, "input-size+768"
    raise SystemExit(
        "error: need a receipt (<output>.json), or --receipt, or --input image"
    )


def make_resolver(scale: float, w: int, h: int, keep_float: bool):
    def xy(x: float, y: float) -> tuple[Any, Any]:
        ox = min(max(x / scale, 0.0), float(w))
        oy = min(max(y / scale, 0.0), float(h))
        if keep_float:
            return round(ox, 2), round(oy, 2)
        return round(ox), round(oy)

    def walk(v: Any) -> Any:
        if isinstance(v, dict):
            if (
                isinstance(v.get("x"), (int, float))
                and isinstance(v.get("y"), (int, float))
            ):
                ox, oy = xy(v["x"], v["y"])
                obj: dict[Any, Any] = {}
                for k, val in v.items():
                    obj[k] = walk(val)  # recurse into other coord-bearing keys
                obj["x"], obj["y"] = ox, oy
                return obj
            return {k: walk(val) for k, val in v.items()}
        if isinstance(v, list):
            if v and all(isinstance(n, (int, float)) for n in v) and len(v) % 2 == 0:
                flat: list[Any] = []
                for i in range(0, len(v), 2):
                    ox, oy = xy(v[i], v[i + 1])
                    flat += [ox, oy]
                return flat
            return [walk(item) for item in v]
        return v

    return walk


def main() -> int:
    ap = argparse.ArgumentParser(
        description="Resolve prep_claude coordinates back to the original image."
    )
    ap.add_argument("--input", type=Path, help="original image (for size/scale)")
    ap.add_argument("--output", type=Path, help="prepped image (its <path>.json receipt is used)")
    ap.add_argument("--receipt", type=Path, help="explicit path to the prep receipt JSON")
    ap.add_argument("--coords", help="inline JSON coordinate structure")
    ap.add_argument("-f", "--file", type=Path, help="JSON file of coordinates")
    ap.add_argument("--out-json", type=Path, help="also write the result here")
    ap.add_argument("--float", action="store_true", help="keep 2-decimal precision (default: round to int)")
    args = ap.parse_args()

    scale, w, h, source = load_transform(args)

    if args.coords is not None:
        raw = args.coords
    elif args.file:
        raw = args.file.read_text()
    else:
        raw = sys.stdin.read()
    if not raw.strip():
        print("error: no coordinates given (--coords, -f, or stdin)", file=sys.stderr)
        return 2
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as e:
        print(f"error: invalid JSON coordinates: {e}", file=sys.stderr)
        return 2

    resolved = make_resolver(scale, w, h, args.float)(data)

    out = json.dumps(resolved)
    print(out)
    if args.out_json:
        args.out_json.write_text(out)
    print(
        f"# transform: scale={scale:.6g} (x{1/scale:.4g}) "
        f"orig={w}x{h} source={source}",
        file=sys.stderr,
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
