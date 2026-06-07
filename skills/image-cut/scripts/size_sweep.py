#!/usr/bin/env python3
"""Probe the size Claude vision operates at WITHOUT internal rescaling.

Method: place one red dot near the BOTTOM-RIGHT corner of an N×N white image
(the most distant point — any rescale shows up biggest there), send it blind
(NO dimensions in the prompt, neutral filename) and ask for the dot's pixel
coords. If the model reports `px` for a dot we put at `N-MARGIN`, the pixel
space it actually processed is:

    M_est = px * N / (N - MARGIN)

M_est tracks N while the image is sent unscaled; it flattens once N exceeds
the model's real processing ceiling (the image got downscaled). The flatten
point ≈ the largest size that round-trips coordinates with no rescale.

Token cap for opus-4.7/4.8: 4784 tokens ≈ 3,588,000 px → square side ≤ 1894.
Long-edge cap: 2576. Docs say bottom/right padded to a multiple of 28.

Usage:
  python scripts/size_sweep.py [--model opus-4.8] [--sizes 1568,1876,...]
                               [--reps 2] [--margin 10] [--timeout 120]
"""
from __future__ import annotations
import argparse
import math
import sys
import time
from pathlib import Path

sys.path.insert(0, str(Path(__file__).resolve().parent))
from validate_vision import (  # noqa: E402
    CLAUDE_MODEL_MAP, DOT_RADIUS, DOT_COLOR, call_claude, parse_xy,
)
from PIL import Image, ImageDraw  # noqa: E402

DEFAULT_SIZES = [1024, 1568, 1792, 1876, 1888, 1894, 1904, 2048, 2304, 2576]


def make_corner_image(path: Path, n: int, margin: int) -> tuple[int, int]:
    img = Image.new("RGB", (n, n), "white")
    dr = ImageDraw.Draw(img)
    cx = cy = n - margin
    dr.ellipse(
        (cx - DOT_RADIUS, cy - DOT_RADIUS, cx + DOT_RADIUS, cy + DOT_RADIUS),
        fill=DOT_COLOR,
    )
    img.save(path)
    return cx, cy


def main() -> int:
    ap = argparse.ArgumentParser(description=__doc__)
    ap.add_argument("--model", default="opus-4.8")
    ap.add_argument("--sizes", default=",".join(str(s) for s in DEFAULT_SIZES))
    ap.add_argument("--reps", type=int, default=2)
    ap.add_argument("--margin", type=int, default=10)
    ap.add_argument("--timeout", type=int, default=120)
    ap.add_argument("--out-dir", type=Path,
                    default=Path(__file__).parent / "_sweep_out")
    args = ap.parse_args()

    cli_id, _ = CLAUDE_MODEL_MAP[args.model]
    args.out_dir.mkdir(parents=True, exist_ok=True)
    sizes = [int(s) for s in args.sizes.split(",") if s.strip()]
    tokens_cap = 4784  # opus-4.7/4.8

    rows = []
    for n in sizes:
        cx, cy = None, None
        for rep in range(args.reps):
            p = args.out_dir / f"{args.model}_{n}_{rep}.png"
            cx, cy = make_corner_image(p, n, args.margin)
            t0 = time.time()
            raw = call_claude(cli_id, p, n, n, args.timeout)
            pred = parse_xy(raw)
            err = None if pred is None else math.hypot(pred[0] - cx, pred[1] - cy)
            # back out the processed pixel space from the reported corner coord
            m_est = None
            if pred is not None:
                m_est = (pred[0] + pred[1]) / 2 * n / (n - args.margin)
            tok = n * n / 750
            row = {
                "n": n, "rep": rep, "expected": (cx, cy), "pred": pred,
                "err_px": err, "err_pct": (None if err is None else 100 * err / n),
                "m_est": m_est, "tokens": tok, "over_cap": tok > tokens_cap,
                "s": round(time.time() - t0, 1), "raw": (raw or "")[:40],
            }
            rows.append(row)
            print(row, flush=True)

    # report
    print("\n  N    tok   cap?  rep  expected     pred        err_px  err%   M_est")
    print("-" * 78)
    for r in rows:
        pred = f"{r['pred'][0]:.0f},{r['pred'][1]:.0f}" if r["pred"] else "—"
        err = f"{r['err_px']:.1f}" if r["err_px"] is not None else "—"
        pct = f"{r['err_pct']:.1f}" if r["err_pct"] is not None else "—"
        me = f"{r['m_est']:.0f}" if r["m_est"] is not None else "—"
        cap = "OVER" if r["over_cap"] else "ok"
        print(f"{r['n']:>5} {r['tokens']:>6.0f} {cap:>5} {r['rep']:>4}  "
              f"{r['expected'][0]},{r['expected'][1]:<8} {pred:>11} "
              f"{err:>7} {pct:>5}  {me:>6}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
