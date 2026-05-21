#!/usr/bin/env python3
"""Fill the most impactful untested gaps in the validation report:

  Run A: bounding-box emission (4 numbers) across 5 models
         — bbox vs single point: does precision change?
  Run B: sonnet stress at 1200² and 1500² (over cap)
         — does haiku's scaling-drift pattern generalize?
  Run C: opus-4.7 at 1568² with anonymized filenames
         — was the 122px anomaly real or filename-leak?
  Run D: gemini-3-flash anonymized at 1024²
         — what's gemini's true noise floor without filename hints?

All test images use UUID-only filenames so the model can't read coords
from paths.
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
CODEX = shutil.which("codex")
GEMINI = shutil.which("gemini")


def make_dot(p, w, h, x, y):
    img = Image.new("RGB", (w, h), "white")
    r = max(8, min(w, h) // 80)
    ImageDraw.Draw(img).ellipse((x - r, y - r, x + r, y + r), fill=(255, 0, 0))
    img.save(p)


def make_box(p, w, h, x1, y1, x2, y2):
    """Outlined rectangle (red, 4-px stroke). Easier for the model
    than a filled rect for measuring corners."""
    img = Image.new("RGB", (w, h), "white")
    d = ImageDraw.Draw(img)
    d.rectangle((x1, y1, x2, y2), outline=(255, 0, 0), width=4)
    img.save(p)


def ask_claude(model, path, w, h, prompt_kind="point"):
    if prompt_kind == "point":
        prompt = (
            f"The image at @{path} is {w} wide and {h} tall. There is one red dot. "
            "Output ONLY x,y of its center as two integers comma separated. No other text."
        )
    else:
        prompt = (
            f"The image at @{path} is {w} wide and {h} tall. There is a red rectangle "
            f"outlined in red. Output ONLY four integers x1,y1,x2,y2 (top-left and "
            f"bottom-right corners of the rectangle). No other text."
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


def ask_codex(path, w, h, prompt_kind="point"):
    if prompt_kind == "point":
        prompt = (
            f"The image is {w} pixels wide and {h} pixels tall. There is one red dot. "
            f"Output ONLY x,y of its center as two integers comma separated, in the "
            f"{w}x{h} coordinate system. No other text."
        )
    else:
        prompt = (
            f"The image is {w} pixels wide and {h} pixels tall. There is a red "
            f"rectangle outlined in red. Output ONLY four integers x1,y1,x2,y2 "
            f"(top-left and bottom-right corners) in the {w}x{h} coordinate system. "
            f"No other text."
        )
    proc = subprocess.run(
        [CODEX, "exec", "--skip-git-repo-check", prompt, "-i", str(path)],
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=240,
    )
    text = proc.stdout.strip() or proc.stderr
    m = re.search(r"\ncodex\n(.+?)\ntokens used", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def ask_gemini(model, path, w, h, prompt_kind="point"):
    if prompt_kind == "point":
        prompt = (
            f"The image at @{path} is {w} wide and {h} tall. There is one red dot. "
            "Output ONLY x,y of its center as two integers comma separated. No other text."
        )
    else:
        prompt = (
            f"The image at @{path} is {w} wide and {h} tall. There is a red "
            f"rectangle outlined in red. Output ONLY four integers x1,y1,x2,y2 "
            f"(top-left and bottom-right corners). No other text."
        )
    p = subprocess.run(
        [GEMINI, "-y", "--skip-trust", "-m", model, "-p", prompt],
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=240,
    )
    return p.stdout.strip() or f"ERR:{p.stderr.strip()[:200]}"


def parse_xy(s):
    m = re.search(r"(-?\d+)\s*[,\s]\s*(-?\d+)", s)
    return (int(m.group(1)), int(m.group(2))) if m else None


def parse_bbox(s):
    nums = re.findall(r"-?\d+", s)
    if len(nums) >= 4:
        return tuple(int(n) for n in nums[:4])
    return None


def run_A_bbox(out_dir):
    print("\n========== RUN A: bbox emission across 5 models ==========\n")
    # Same image fed to each model; different sizes are each model's safe size.
    cases = [
        ("claude-haiku-4-5",   "claude", 1064, 1064),
        ("claude-sonnet-4-6",  "claude", 1064, 1064),
        ("claude-opus-4-7",    "claude", 1876, 1876),
        ("gemini-3-flash-preview", "gemini", 1024, 1024),
        ("codex_default",      "codex",  768, 768),
    ]
    for (model_id, family, w, h) in cases:
        # Bbox placed at known coords; same proportions across sizes.
        x1 = int(w * 0.20)
        y1 = int(h * 0.30)
        x2 = int(w * 0.70)
        y2 = int(h * 0.65)
        path = out_dir / f"img_{uuid.uuid4().hex[:12]}.png"
        make_box(path, w, h, x1, y1, x2, y2)
        t0 = time.time()
        try:
            if family == "claude":
                raw = ask_claude(model_id, path, w, h, "bbox")
            elif family == "gemini":
                raw = ask_gemini(model_id, path, w, h, "bbox")
            else:
                raw = ask_codex(path, w, h, "bbox")
        except Exception as e:
            print(f"  {model_id:30s} {w}x{h}  EXC {e!r}")
            continue
        bbox = parse_bbox(raw)
        elapsed = time.time() - t0
        if bbox:
            err = math.sqrt(
                (bbox[0]-x1)**2 + (bbox[1]-y1)**2
                + (bbox[2]-x2)**2 + (bbox[3]-y2)**2
            )
            d = [bbox[0]-x1, bbox[1]-y1, bbox[2]-x2, bbox[3]-y2]
            print(
                f"  {model_id:30s} {w}x{h}  "
                f"expected ({x1},{y1},{x2},{y2})  got ({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})  "
                f"diffs {d}  L2_err={err:.1f}px  {elapsed:.1f}s"
            )
        else:
            print(f"  {model_id:30s} {w}x{h}  PARSE FAIL: {raw[:80]}  {elapsed:.1f}s")


def run_corners(name, model_id, family, w, h, out_dir, positions=None):
    """4-corner point test on a given (model, size)."""
    if positions is None:
        m = max(20, min(w, h) // 40)
        positions = [(m, m), (w-m, m), (m, h-m), (w-m, h-m)]
    print(f"\n=== {name} @ {w}x{h} ===")
    errs = []
    for (gx, gy) in positions:
        path = out_dir / f"img_{uuid.uuid4().hex[:12]}.png"
        make_dot(path, w, h, gx, gy)
        t0 = time.time()
        try:
            if family == "claude":
                raw = ask_claude(model_id, path, w, h, "point")
            elif family == "gemini":
                raw = ask_gemini(model_id, path, w, h, "point")
            else:
                raw = ask_codex(path, w, h, "point")
        except Exception as e:
            print(f"  exp ({gx},{gy}) EXC {e!r}")
            continue
        pred = parse_xy(raw)
        if pred:
            err = math.hypot(pred[0]-gx, pred[1]-gy)
            errs.append(err)
            print(
                f"  exp ({gx:>4},{gy:>4})  got ({pred[0]:>5},{pred[1]:>5})  "
                f"dx={pred[0]-gx:+4d} dy={pred[1]-gy:+4d}  err={err:.1f}px  {time.time()-t0:.1f}s"
            )
        else:
            print(f"  exp ({gx},{gy}) PARSE FAIL: {raw[:60]}")
    if errs:
        print(f"  → max={max(errs):.1f}px  avg={sum(errs)/len(errs):.1f}px")


def run_B_sonnet_stress(out_dir):
    print("\n========== RUN B: sonnet over-cap stress ==========\n")
    for (w, h) in [(1200, 1200), (1500, 1500)]:
        run_corners(f"sonnet over_{w*h/750/1568:.1f}x", "claude-sonnet-4-6", "claude", w, h, out_dir)


def run_C_opus_1568(out_dir):
    print("\n========== RUN C: opus-4.7 @ 1568² anomaly recheck ==========\n")
    run_corners("opus-4.7 @1568²", "claude-opus-4-7", "claude", 1568, 1568, out_dir)


def run_D_gemini_floor(out_dir):
    print("\n========== RUN D: gemini-3-flash @ 1024² anonymized noise floor ==========\n")
    run_corners("gemini @1024²", "gemini-3-flash-preview", "gemini", 1024, 1024, out_dir)


def main():
    out_dir = Path(__file__).parent / "_gaps_out"
    out_dir.mkdir(exist_ok=True)
    run_A_bbox(out_dir)
    run_B_sonnet_stress(out_dir)
    run_C_opus_1568(out_dir)
    run_D_gemini_floor(out_dir)


if __name__ == "__main__":
    main()
