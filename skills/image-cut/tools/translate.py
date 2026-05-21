#!/usr/bin/env python3
"""Translate a point or bbox across a chain of receipts.

Usage:
  translate.py --chain R1.json [R2.json ...]
               (--point x,y | --bbox x1,y1,x2,y2)
               --to global|local
               [--round]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def parse_point(s: str) -> tuple[float, float]:
    parts = s.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"point must be x,y — got: {s!r}")
    return float(parts[0]), float(parts[1])


def parse_bbox(s: str) -> tuple[float, float, float, float]:
    parts = s.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"bbox must be x1,y1,x2,y2 — got: {s!r}"
        )
    return tuple(float(p) for p in parts)  # type: ignore[return-value]


def map_local_to_input(op: dict, local: tuple[float, float]) -> tuple[float, float]:
    """Apply one op's local → input transform."""
    lx, ly = local
    kind = op["op"]
    if kind == "crop":
        x1, y1, _, _ = op["bbox"]
        return lx + x1, ly + y1
    if kind == "pad":
        pad = op["pad"]
        return lx - pad["left"], ly - pad["top"]
    if kind == "resize":
        in_w, in_h = op["in_size"]
        out_w, out_h = op["out_size"]
        return lx * in_w / out_w, ly * in_h / out_h
    if kind == "vision_prep":
        # right/bottom pad only — no origin offset. Just undo the scale.
        scale = op["scale"]
        return lx / scale, ly / scale
    raise ValueError(f"unknown op: {kind}")


def map_input_to_local(op: dict, inp: tuple[float, float]) -> tuple[float, float]:
    """Apply the inverse of one op (input → local)."""
    ix, iy = inp
    kind = op["op"]
    if kind == "crop":
        x1, y1, _, _ = op["bbox"]
        return ix - x1, iy - y1
    if kind == "pad":
        pad = op["pad"]
        return ix + pad["left"], iy + pad["top"]
    if kind == "resize":
        in_w, in_h = op["in_size"]
        out_w, out_h = op["out_size"]
        return ix * out_w / in_w, iy * out_h / in_h
    if kind == "vision_prep":
        scale = op["scale"]
        return ix * scale, iy * scale
    raise ValueError(f"unknown op: {kind}")


def load_receipts(paths: list[Path]) -> list[dict]:
    receipts = []
    for p in paths:
        if not p.exists():
            raise SystemExit(f"error: receipt not found: {p}")
        receipts.append(json.loads(p.read_text()))
    for i in range(1, len(receipts)):
        prev_out = receipts[i - 1]["output"]["path"]
        this_in = receipts[i]["input"]["path"]
        if prev_out != this_in:
            raise SystemExit(
                f"error: chain mismatch — receipt[{i-1}].output.path "
                f"{prev_out!r} != receipt[{i}].input.path {this_in!r}"
            )
    return receipts


def translate_point_to_global(
    receipts: list[dict], pt: tuple[float, float]
) -> tuple[float, float]:
    """Walk chain backwards (final → original) applying local→input."""
    cur = pt
    for r in reversed(receipts):
        cur = map_local_to_input(r["op"], cur)
    return cur


def translate_point_to_local(
    receipts: list[dict], pt: tuple[float, float]
) -> tuple[float, float]:
    """Walk chain forwards (original → final) applying input→local."""
    cur = pt
    for r in receipts:
        cur = map_input_to_local(r["op"], cur)
    return cur


def maybe_round(vals: list[float], do_round: bool) -> list:
    if do_round:
        return [int(round(v)) for v in vals]
    return list(vals)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Translate a point or bbox across a chain of receipts."
    )
    parser.add_argument("--chain", type=Path, nargs="+", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--point", type=parse_point)
    group.add_argument("--bbox", type=parse_bbox)
    parser.add_argument("--to", choices=["global", "local"], required=True)
    parser.add_argument("--round", action="store_true")
    args = parser.parse_args()

    try:
        receipts = load_receipts(args.chain)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2

    translate = (
        translate_point_to_global if args.to == "global" else translate_point_to_local
    )

    if args.point is not None:
        out = translate(receipts, args.point)
        key = args.to
        print(json.dumps({key: maybe_round(list(out), args.round)}))
    else:
        x1, y1, x2, y2 = args.bbox
        p1 = translate(receipts, (x1, y1))
        p2 = translate(receipts, (x2, y2))
        bx1, by1 = min(p1[0], p2[0]), min(p1[1], p2[1])
        bx2, by2 = max(p1[0], p2[0]), max(p1[1], p2[1])
        key = args.to
        print(json.dumps({key: maybe_round([bx1, by1, bx2, by2], args.round)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
