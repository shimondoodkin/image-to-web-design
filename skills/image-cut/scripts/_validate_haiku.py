#!/usr/bin/env python3
"""Validate the documented Claude size table against claude-haiku-4-5.

Sweeps a list of (w, h) sizes and tests the 4 corners on each.
0–3px errors per corner = sizing is correct.
>10px systematic offset on multiple corners = scaling artifact / wrong size.
"""
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw

CLAUDE = shutil.which("claude")
assert CLAUDE, "claude CLI not on PATH"

MODEL = "claude-haiku-4-5"

SIZES = [
    # (w, h, label)
    (1064, 1064, "1:1 baseline (known good)"),
    (1092, 1092, "1:1 max (formula output)"),
    (1260, 952, "4:3 max"),
    (1344, 896, "3:2 max"),
    (1456, 840, "16:9 max"),
    (1540, 784, "2:1 max"),
    (1568, 784, "2:1 long-edge max"),
]


def make(p, w, h, x, y):
    img = Image.new("RGB", (w, h), "white")
    r = max(4, min(w, h) // 100)
    ImageDraw.Draw(img).ellipse((x - r, y - r, x + r, y + r), fill=(255, 0, 0))
    img.save(p)


def ask(model, path, w, h):
    prompt = (
        f"The image at @{path} is {w} wide and {h} tall. There is one red dot. "
        "Output ONLY x,y of its center as two integers comma separated. No other text."
    )
    p = subprocess.run(
        [
            CLAUDE, "--print",
            "--model", model,
            "--add-dir", str(Path(path).parent),
            "--disable-slash-commands",
            "--dangerously-skip-permissions",
        ],
        input=prompt,
        capture_output=True, text=True, timeout=180,
    )
    return p.stdout.strip()


def main():
    out_dir = Path(__file__).parent / "_validate_haiku_out"
    out_dir.mkdir(exist_ok=True)
    results = {}
    for (w, h, label) in SIZES:
        margin = max(20, min(w, h) // 40)
        corners = [
            (margin, margin),
            (w - margin, margin),
            (margin, h - margin),
            (w - margin, h - margin),
        ]
        errs = []
        print(f"\n=== {MODEL} at {w}x{h} ({label}) ===", flush=True)
        for (gx, gy) in corners:
            path = out_dir / f"h_{w}x{h}_{gx}_{gy}.png"
            make(path, w, h, gx, gy)
            t0 = time.time()
            try:
                raw = ask(MODEL, path, w, h)
            except Exception as e:
                print(f"  ({gx},{gy}) EXC {e!r}", flush=True)
                continue
            m = re.search(r"(-?\d+)\s*[,\s]\s*(-?\d+)", raw)
            if m:
                pred = (int(m.group(1)), int(m.group(2)))
                err = math.hypot(pred[0] - gx, pred[1] - gy)
                errs.append(err)
                print(
                    f"  ({gx},{gy}) -> {raw.strip()[:30]} "
                    f"[err={err:.1f}px {time.time()-t0:.1f}s]",
                    flush=True,
                )
            else:
                print(f"  ({gx},{gy}) PARSE FAIL: {raw[:60]}", flush=True)
        if errs:
            results[(w, h, label)] = (max(errs), sum(errs) / len(errs))

    print("\n=== Summary ===")
    print(f"{'size':>11}  {'max':>7}  {'avg':>7}  verdict   label")
    for (w, h, label), (mx, avg) in results.items():
        flag = "OK" if mx <= 5 else ("NOISY" if mx <= 20 else "SCALED")
        size_s = f"{w}x{h}"
        print(f"{size_s:>11}  {mx:>6.1f}px {avg:>6.1f}px  {flag:<8}  {label}")


if __name__ == "__main__":
    main()
