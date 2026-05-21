#!/usr/bin/env python3
"""Confirm whether 800x600 vs 812x616 (28-aligned) gives a scaling signal."""
import math
import re
import shutil
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw

CLAUDE = shutil.which("claude")
MODEL = "claude-haiku-4-5"

# Compare a non-28-mult size against its 28-aligned ceil-up equivalent.
# Same dot size for both so visual noise is comparable.
DOT_RADIUS = 8

CASES = [
    ("800x600_not_aligned", 800, 600),
    ("812x616_aligned",     812, 616),
    ("784x588_aligned_down", 784, 588),  # mult of 28, smaller than 800x600
]


def make(p, w, h, x, y):
    img = Image.new("RGB", (w, h), "white")
    ImageDraw.Draw(img).ellipse(
        (x - DOT_RADIUS, y - DOT_RADIUS, x + DOT_RADIUS, y + DOT_RADIUS),
        fill=(255, 0, 0),
    )
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
    out_dir = Path(__file__).parent / "_disambig2_out"
    out_dir.mkdir(exist_ok=True)

    for (label, w, h) in CASES:
        # 8 positions: 4 corners + 4 mid-edges
        m = max(20, min(w, h) // 30)
        positions = [
            (m, m),                # TL
            (w - m, m),            # TR
            (m, h - m),            # BL
            (w - m, h - m),        # BR
            (w // 2, m),           # top-mid
            (w // 2, h - m),       # bottom-mid
            (m, h // 2),           # left-mid
            (w - m, h // 2),       # right-mid
        ]
        results = []
        print(
            f"\n=== {label}: {w}x{h} (tokens={w*h/750:.0f}, "
            f"mult28={w%28==0 and h%28==0}) ===",
            flush=True,
        )
        for (gx, gy) in positions:
            path = out_dir / f"{label}_{gx}_{gy}.png"
            make(path, w, h, gx, gy)
            t0 = time.time()
            try:
                raw = ask(MODEL, path, w, h)
            except Exception as e:
                print(f"  ({gx},{gy}) EXC {e!r}", flush=True)
                continue
            mt = re.search(r"(-?\d+)\s*[,\s]\s*(-?\d+)", raw)
            if mt:
                pred = (int(mt.group(1)), int(mt.group(2)))
                err = math.hypot(pred[0] - gx, pred[1] - gy)
                dx = pred[0] - gx
                dy = pred[1] - gy
                results.append((gx, gy, pred[0], pred[1], dx, dy, err))
                print(
                    f"  ({gx},{gy}) -> {raw.strip()[:30]}  "
                    f"dx={dx:+d} dy={dy:+d} err={err:.1f}px {time.time()-t0:.1f}s",
                    flush=True,
                )

        if results:
            errs = [r[6] for r in results]
            dxs = [r[4] for r in results]
            dys = [r[5] for r in results]
            print(
                f"  → max={max(errs):.1f}  avg={sum(errs)/len(errs):.1f}  "
                f"mean_dx={sum(dxs)/len(dxs):+.1f}  mean_dy={sum(dys)/len(dys):+.1f}",
                flush=True,
            )


if __name__ == "__main__":
    main()
