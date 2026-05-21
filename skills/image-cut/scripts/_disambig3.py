#!/usr/bin/env python3
"""Re-run the disambiguation with ANONYMOUS filenames so Claude can't
extract coordinates from the path.

Same logic as _disambig.py but uses uuid-based filenames so the path
contains no information about the dot's position.
"""
import math
import re
import shutil
import subprocess
import time
import uuid
from pathlib import Path
from PIL import Image, ImageDraw

CLAUDE = shutil.which("claude")
MODEL = "claude-haiku-4-5"
DOT_RADIUS = 8

CASES = [
    ("baseline_good",     1064, 1064),
    ("baseline_bad",      1092, 1092),
    ("not_28_under_cap",  1084, 1084),
    ("not_28_well_under", 800, 600),
    ("aligned_812x616",   812, 616),
]


def make(p, w, h, x, y):
    img = Image.new("RGB", (w, h), "white")
    ImageDraw.Draw(img).ellipse(
        (x - DOT_RADIUS, y - DOT_RADIUS, x + DOT_RADIUS, y + DOT_RADIUS),
        fill=(255, 0, 0),
    )
    img.save(p)


def ask(model, path, w, h):
    # Path is anonymous (uuid-only) — no coordinates leak.
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
    out_dir = Path(__file__).parent / "_disambig3_out"
    out_dir.mkdir(exist_ok=True)

    for (label, w, h) in CASES:
        m = max(20, min(w, h) // 30)
        positions = [
            (m, m),                # TL
            (w - m, m),            # TR
            (m, h - m),            # BL
            (w - m, h - m),        # BR
        ]
        results = []
        print(
            f"\n=== {label}: {w}x{h} (tokens={w*h/750:.0f}, "
            f"mult28={w%28==0 and h%28==0}) ===",
            flush=True,
        )
        for (gx, gy) in positions:
            # Anonymous filename — no leak of coordinates
            path = out_dir / f"img_{uuid.uuid4().hex[:12]}.png"
            make(path, w, h, gx, gy)
            t0 = time.time()
            try:
                raw = ask(MODEL, path, w, h)
            except Exception as e:
                print(f"  expected ({gx},{gy}) EXC {e!r}", flush=True)
                continue
            mt = re.search(r"(-?\d+)\s*[,\s]\s*(-?\d+)", raw)
            if mt:
                pred = (int(mt.group(1)), int(mt.group(2)))
                err = math.hypot(pred[0] - gx, pred[1] - gy)
                dx = pred[0] - gx
                dy = pred[1] - gy
                results.append((gx, gy, pred[0], pred[1], dx, dy, err))
                print(
                    f"  expected ({gx:>4},{gy:>4})  got ({pred[0]:>4},{pred[1]:>4})  "
                    f"dx={dx:+d} dy={dy:+d}  err={err:.1f}px  {time.time()-t0:.1f}s",
                    flush=True,
                )

        if results:
            errs = [r[6] for r in results]
            dxs = [r[4] for r in results]
            dys = [r[5] for r in results]
            print(
                f"  → max={max(errs):.1f}px  avg={sum(errs)/len(errs):.1f}px  "
                f"mean_dx={sum(dxs)/len(dxs):+.1f}  mean_dy={sum(dys)/len(dys):+.1f}",
                flush=True,
            )


if __name__ == "__main__":
    main()
