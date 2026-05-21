#!/usr/bin/env python3
"""Disambiguate Claude's rescale trigger.

Theories:
  A) Rescales if SENT_size > token cap (pre-pad).
  B) Rescales if post-internal-pad-to-28 > token cap.
  C) Requires sent_size to be an exact multiple of 28 to avoid rescale.

Test cases (all run on haiku, 1568 token cap = 1,176,000 pixels):
  baseline_good:   1064² = 1064 mult-of-28, 1509 tokens (under cap)   → expect 0px
  baseline_bad:    1092² = 1092 mult-of-28, 1590 tokens (over cap)    → expect drift
  not_28_under:    1084² = NOT mult of 28, 1567 tokens (under cap)
                   post-pad would be 1092² = 1590 (over cap)
                     → under (A): accurate (sent fits)
                     → under (B): drift (post-pad over cap)
                     → under (C): drift (not 28-mult)
  not_28_well_under: 800×600 = NOT mult of 28, 640 tokens (well under)
                     post-pad 812×616 = 667 tokens (still well under)
                     → under (A) or (B): accurate
                     → under (C): drift
"""
import math
import re
import shutil
import subprocess
import time
from pathlib import Path
from PIL import Image, ImageDraw

CLAUDE = shutil.which("claude")
MODEL = "claude-haiku-4-5"

CASES = [
    ("baseline_good",     1064, 1064),
    ("baseline_bad",      1092, 1092),
    ("not_28_under_cap",  1084, 1084),
    ("not_28_well_under", 800, 600),
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
    out_dir = Path(__file__).parent / "_disambig_out"
    out_dir.mkdir(exist_ok=True)

    for (label, w, h) in CASES:
        # Test all 4 corners
        margin = max(20, min(w, h) // 40)
        corners = [
            (margin, margin),
            (w - margin, margin),
            (margin, h - margin),
            (w - margin, h - margin),
        ]
        errs = []
        print(f"\n=== {label}: {w}x{h} (tokens={w*h/750:.0f}, mult28={w%28==0 and h%28==0}) ===",
              flush=True)
        for (gx, gy) in corners:
            path = out_dir / f"{label}_{gx}_{gy}.png"
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
                print(f"  ({gx},{gy}) -> {raw.strip()[:30]} [err={err:.1f}px {time.time()-t0:.1f}s]",
                      flush=True)
            else:
                print(f"  ({gx},{gy}) PARSE FAIL: {raw[:60]}", flush=True)
        if errs:
            print(f"  max={max(errs):.1f}px avg={sum(errs)/len(errs):.1f}px", flush=True)

    print("\n=== Interpretation ===")
    print("If not_28_under_cap is accurate (≤5px max) → theory A: pre-pad cap is the trigger")
    print("If not_28_well_under is accurate but not_28_under is bad → theory B: post-pad cap")
    print("If both not_28_* are bad → theory C: need exact 28-multiple")


if __name__ == "__main__":
    main()
