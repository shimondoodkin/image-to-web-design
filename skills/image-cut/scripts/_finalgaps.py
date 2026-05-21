#!/usr/bin/env python3
"""Fill remaining gaps from the validation report:

  Run E: variance on opus-4.7 bbox (5 repeats of bbox test at 1876²)
         — is the 195px L2 error real or a one-shot bad guess?
  Run F: other Gemini models — gemini-3.1-pro-preview,
         gemini-3.1-flash-lite-preview, gemini-2.5-pro, gemini-2.5-flash
         — do they all hit 0px like 3-flash-preview?
  Run G: OpenAI codex at 3000² — what coord space does it use over 2048?
  Run H: opus-4.7 extreme over-cap threshold — 2500², 3500²
         — where does it flip to inconsistent behavior?

All filenames are UUID-only.
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
    img = Image.new("RGB", (w, h), "white")
    ImageDraw.Draw(img).rectangle((x1, y1, x2, y2), outline=(255, 0, 0), width=4)
    img.save(p)


def ask_claude(model, path, w, h, kind="point"):
    if kind == "point":
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


def ask_codex(path, w, h, kind="point"):
    if kind == "point":
        prompt = (
            f"The image is {w} pixels wide and {h} pixels tall. There is one red dot. "
            f"Output ONLY x,y of its center as two integers comma separated, in the "
            f"{w}x{h} coordinate system. No other text."
        )
    else:
        prompt = (
            f"The image is {w} pixels wide and {h} pixels tall. There is a red "
            f"rectangle outlined in red. Output ONLY four integers x1,y1,x2,y2 "
            f"(top-left and bottom-right corners) in the {w}x{h} coordinate system."
        )
    proc = subprocess.run(
        [CODEX, "exec", "--skip-git-repo-check", prompt, "-i", str(path)],
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=240,
    )
    text = proc.stdout.strip() or proc.stderr
    m = re.search(r"\ncodex\n(.+?)\ntokens used", text, re.DOTALL)
    return m.group(1).strip() if m else text.strip()


def ask_gemini(model, path, w, h, kind="point"):
    if kind == "point":
        prompt = (
            f"The image at @{path} is {w} wide and {h} tall. There is one red dot. "
            "Output ONLY x,y of its center as two integers comma separated. No other text."
        )
    else:
        prompt = (
            f"The image at @{path} is {w} wide and {h} tall. There is a red "
            f"rectangle outlined in red. Output ONLY four integers x1,y1,x2,y2."
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
    return tuple(int(n) for n in nums[:4]) if len(nums) >= 4 else None


def run_E_opus_bbox_variance(out_dir):
    print("\n========== RUN E: opus-4.7 bbox variance (N=5 same image) ==========\n")
    w, h = 1876, 1876
    x1, y1, x2, y2 = int(w*0.20), int(h*0.30), int(w*0.70), int(h*0.65)
    print(f"  bbox expected: ({x1},{y1},{x2},{y2})")
    results = []
    for trial in range(5):
        path = out_dir / f"img_{uuid.uuid4().hex[:12]}.png"
        make_box(path, w, h, x1, y1, x2, y2)
        t0 = time.time()
        try:
            raw = ask_claude("claude-opus-4-7", path, w, h, "bbox")
        except Exception as e:
            print(f"  trial {trial+1}: EXC {e!r}")
            continue
        bbox = parse_bbox(raw)
        elapsed = time.time() - t0
        if bbox:
            L2 = math.sqrt((bbox[0]-x1)**2 + (bbox[1]-y1)**2 + (bbox[2]-x2)**2 + (bbox[3]-y2)**2)
            diffs = [bbox[0]-x1, bbox[1]-y1, bbox[2]-x2, bbox[3]-y2]
            results.append((trial, bbox, diffs, L2))
            print(f"  trial {trial+1}: got ({bbox[0]},{bbox[1]},{bbox[2]},{bbox[3]})  diffs {diffs}  L2={L2:.1f}px  {elapsed:.1f}s")
        else:
            print(f"  trial {trial+1}: PARSE FAIL: {raw[:80]}")
    if results:
        l2s = [r[3] for r in results]
        print(f"  → L2 min={min(l2s):.1f}  max={max(l2s):.1f}  avg={sum(l2s)/len(l2s):.1f}px (N={len(l2s)})")


def run_F_other_gemini(out_dir):
    print("\n========== RUN F: other Gemini models @ 1024² ==========\n")
    w, h = 1024, 1024
    m = 25
    corners = [(m, m), (w-m, m), (m, h-m), (w-m, h-m)]
    models = [
        "gemini-3.1-pro-preview",
        "gemini-3.1-flash-lite-preview",
        "gemini-2.5-pro",
        "gemini-2.5-flash",
        "gemini-2.5-flash-lite",
    ]
    for model in models:
        print(f"\n--- {model} @ {w}x{h} ---")
        errs = []
        for (gx, gy) in corners:
            path = out_dir / f"img_{uuid.uuid4().hex[:12]}.png"
            make_dot(path, w, h, gx, gy)
            t0 = time.time()
            try:
                raw = ask_gemini(model, path, w, h, "point")
            except Exception as e:
                print(f"  exp ({gx},{gy}) EXC {e!r}")
                continue
            pred = parse_xy(raw)
            if pred:
                err = math.hypot(pred[0]-gx, pred[1]-gy)
                errs.append(err)
                print(f"  exp ({gx:>4},{gy:>4}) got ({pred[0]:>4},{pred[1]:>4}) err={err:.1f}px {time.time()-t0:.1f}s")
            else:
                print(f"  exp ({gx},{gy}) PARSE FAIL: {raw[:60]}")
        if errs:
            print(f"  → max={max(errs):.1f}  avg={sum(errs)/len(errs):.1f}px")


def run_G_openai_over_2048(out_dir):
    print("\n========== RUN G: OpenAI codex @ 3000x3000 (over 2048 long-edge) ==========\n")
    w, h = 3000, 3000
    # Place dot at far positions
    corners = [(750, 750), (2250, 750), (750, 2250), (2250, 2250)]
    # OpenAI: at >2048, image first scaled to fit 2048², then shortest side scaled to 768.
    # So a 3000² square → 2048² (s=0.683) → 768² (s2=0.375). Final scale ≈ 0.256.
    expected_scale = (2048 / 3000) * (768 / 2048)
    print(f"  if scaled, expected final scale = {expected_scale:.3f}")
    for (gx, gy) in corners:
        path = out_dir / f"img_{uuid.uuid4().hex[:12]}.png"
        make_dot(path, w, h, gx, gy)
        t0 = time.time()
        try:
            raw = ask_codex(path, w, h, "point")
        except Exception as e:
            print(f"  exp ({gx},{gy}) EXC {e!r}")
            continue
        pred = parse_xy(raw)
        if pred:
            err_orig = math.hypot(pred[0]-gx, pred[1]-gy)
            sx, sy = gx*expected_scale, gy*expected_scale
            err_scaled = math.hypot(pred[0]-sx, pred[1]-sy)
            closer = "ORIG" if err_orig < err_scaled else "SCALED"
            print(f"  exp ({gx},{gy})  got ({pred[0]},{pred[1]})  err_orig={err_orig:.0f}  err_scaled={err_scaled:.0f}  closer={closer}  {time.time()-t0:.1f}s")
        else:
            print(f"  exp ({gx},{gy}) PARSE FAIL: {raw[:60]}")


def run_H_opus_extreme(out_dir):
    print("\n========== RUN H: opus-4.7 extreme over-cap (2500² & 3500²) ==========\n")
    cases = [
        (2500, 2500),  # 8333 tokens, 1.7x over opus-4.7 cap
        (3500, 3500),  # 16333 tokens, 3.4x over
    ]
    for (w, h) in cases:
        # opus-4.7 cap: 4784 tokens, max long edge 2576
        long_edge_scale = min(1.0, 2576/max(w,h))
        token_scale = math.sqrt(4784*750/(w*h))
        expected_scale = min(1.0, long_edge_scale, token_scale)
        m = max(30, min(w, h) // 40)
        corners = [(m, m), (w-m, m), (m, h-m), (w-m, h-m)]
        print(f"\n--- opus-4.7 @ {w}x{h} (predicted scale={expected_scale:.3f}) ---")
        for (gx, gy) in corners:
            path = out_dir / f"img_{uuid.uuid4().hex[:12]}.png"
            make_dot(path, w, h, gx, gy)
            t0 = time.time()
            try:
                raw = ask_claude("claude-opus-4-7", path, w, h, "point")
            except Exception as e:
                print(f"  exp ({gx},{gy}) EXC {e!r}")
                continue
            pred = parse_xy(raw)
            if pred:
                err_orig = math.hypot(pred[0]-gx, pred[1]-gy)
                sx, sy = gx*expected_scale, gy*expected_scale
                err_scaled = math.hypot(pred[0]-sx, pred[1]-sy)
                closer = "ORIG" if err_orig < err_scaled else "SCALED"
                print(f"  exp ({gx:>4},{gy:>4})  got ({pred[0]:>4},{pred[1]:>4})  err_orig={err_orig:.0f}  err_scaled={err_scaled:.0f}  closer={closer}  {time.time()-t0:.1f}s")
            else:
                print(f"  exp ({gx},{gy}) PARSE FAIL: {raw[:60]}")


def main():
    out_dir = Path(__file__).parent / "_finalgaps_out"
    out_dir.mkdir(exist_ok=True)
    run_E_opus_bbox_variance(out_dir)
    run_F_other_gemini(out_dir)
    run_G_openai_over_2048(out_dir)
    run_H_opus_extreme(out_dir)


if __name__ == "__main__":
    main()
