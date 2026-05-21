#!/usr/bin/env python3
"""Stress test: sizes way over cap should trigger systematic scaling.

Sonnet cap: 1568 tokens (1,176,000 px). Test with:
- 2000x2000 (5333 tokens, 3.4x over cap)
- 3000x3000 (12000 tokens, 7.6x over cap)
- 4000x4000 (21333 tokens, 13.6x over cap)

If Claude rescales to fit cap (~1084² for square), coords returned will
either be in the SCALED space (so 1500 in source → ~813) or in some
remapped space. Either way, large systematic drift should emerge if
scaling is happening.

Uses anonymized UUID filenames to prevent filename-leak cheating.
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

# (label, w, h)
CASES = [
    ("over_1.3x", 1200, 1200),  # tokens 1920, ~1.2x over
    ("over_2x",   1500, 1500),  # tokens 3000, ~1.9x over
    ("over_3x",   2000, 2000),  # tokens 5333, ~3.4x over
    ("over_8x",   3000, 3000),  # tokens 12000, ~7.6x over
]


def make(p, w, h, x, y):
    img = Image.new("RGB", (w, h), "white")
    # Scale dot radius with image size so it's visible
    r = max(8, min(w, h) // 80)
    ImageDraw.Draw(img).ellipse((x - r, y - r, x + r, y + r), fill=(255, 0, 0))
    img.save(p)


def ask(model, path, w, h):
    prompt = (
        f"The image at @{path} is {w} pixels wide and {h} pixels tall. "
        f"There is one red dot. Output ONLY x,y of its center as two integers "
        f"comma separated, in the {w}x{h} coordinate system. No other text."
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
    out_dir = Path(__file__).parent / "_stress_out"
    out_dir.mkdir(exist_ok=True)

    for (label, w, h) in CASES:
        # 4 positions spread across the image (in source coords)
        positions = [
            (w // 4, h // 4),         # quarter
            (3 * w // 4, h // 4),     # 3-quarter top-right
            (w // 4, 3 * h // 4),     # 3-quarter bottom-left
            (3 * w // 4, 3 * h // 4), # 3-quarter bottom-right
        ]
        # Expected scale if Claude downscales to ~1084² for square
        tokens = w * h / 750
        expected_scale = min(1.0, math.sqrt(1176000 / (w * h)))
        results = []
        print(
            f"\n=== {label}: {w}x{h} (tokens={tokens:.0f}, "
            f"if-scaled scale≈{expected_scale:.3f}, scaled≈{round(w*expected_scale)}²) ===",
            flush=True,
        )
        for (gx, gy) in positions:
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
                # What would we get if model returned scaled coords?
                scaled_x = gx * expected_scale
                scaled_y = gy * expected_scale
                # Is the predicted point closer to original or to scaled-down?
                src_dist = math.hypot(pred[0] - gx, pred[1] - gy)
                scl_dist = math.hypot(pred[0] - scaled_x, pred[1] - scaled_y)
                interp = "ORIG" if src_dist < scl_dist else "SCALED"
                results.append((gx, gy, pred[0], pred[1], dx, dy, err, interp))
                print(
                    f"  expected ({gx:>4},{gy:>4})  got ({pred[0]:>5},{pred[1]:>5})  "
                    f"dx={dx:+5d} dy={dy:+5d}  err={err:.1f}px  "
                    f"closer-to={interp}  {time.time()-t0:.1f}s",
                    flush=True,
                )

        if results:
            errs = [r[6] for r in results]
            print(
                f"  → max={max(errs):.1f}px  avg={sum(errs)/len(errs):.1f}px  "
                f"closer-to: {sum(1 for r in results if r[7]=='ORIG')}/{len(results)} ORIG",
                flush=True,
            )


if __name__ == "__main__":
    main()
