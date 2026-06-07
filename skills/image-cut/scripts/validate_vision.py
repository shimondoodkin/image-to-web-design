#!/usr/bin/env python3
"""Validate the vision_prep pipeline against real vision models via CLI.

Generates known-marker test images at each model's expected vision-safe size,
sends each to the model through the `claude` and `codex` CLI tools, parses
the predicted coordinates, and reports per-model accuracy.

A small error (a few pixels) → vision pipeline is well-aligned.
A large systematic offset → image was rescaled internally; our target size
is off for that model.

Usage:
  python scripts/validate_vision.py [--claude-models opus-4.7,sonnet,haiku]
                                    [--codex-models gpt-5,gpt-5-mini]
                                    [--positions 3]
                                    [--out-dir scripts/_validate_out]
                                    [--timeout 90]

Requires the `claude` and `codex` CLIs on PATH and authenticated.
Makes real API calls. Costs money. Run intentionally.
"""
from __future__ import annotations
import argparse
import json
import math
import re
import shutil
import subprocess
import sys
import time
from pathlib import Path
from PIL import Image, ImageDraw


def resolve_cmd(name: str) -> str:
    """Resolve a CLI command — handles Windows .cmd shims (e.g. codex.CMD)."""
    found = shutil.which(name)
    if not found:
        raise FileNotFoundError(f"{name!r} not found on PATH")
    return found

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "tools"))
from vision_prep import MODEL_LIMITS  # noqa: E402


# Claude CLI uses model IDs like "claude-opus-4-7", "claude-sonnet-4-6".
CLAUDE_MODEL_MAP: dict[str, tuple[str, str]] = {
    # short_name → (cli_model_id, vision_prep_key)
    "opus-4.8": ("claude-opus-4-8", "opus-4.8"),
    "opus-4.7": ("claude-opus-4-7", "opus-4.7"),
    "sonnet": ("claude-sonnet-4-6", "sonnet"),
    "haiku": ("claude-haiku-4-5", "haiku"),
}

DOT_RADIUS = 8
DOT_COLOR = (255, 0, 0)
PROMPT = (
    "There is exactly one red dot in the attached image. Output ONLY the dot "
    "center's pixel coordinates as two integers separated by a comma in the "
    "form 'x,y' — no other text, no labels, no explanation, no markdown. "
    "Do not state the image dimensions."
)


def safe_square_side(vp_key: str) -> int:
    """Square side at the model's max-safe size (mult of 28)."""
    limits = MODEL_LIMITS[vp_key]
    side = min(limits["max_long_edge"], int(math.sqrt(limits["max_tokens"] * 750)))
    return (side // 28) * 28


# OpenAI vision (detail:high) processes images at:
#   1. Scale to fit within 2048x2048 (preserving aspect)
#   2. Scale so shortest side = 768
#   3. Tile in 512px squares (cost only, dims unchanged)
# For a square input, native processing size is 768x768. Sending at exactly
# 768x768 means no internal rescale → most accurate coords.
OPENAI_SQUARE_SIDE = 768


def generate_image(out_path: Path, w: int, h: int, dot_xy: tuple[int, int]):
    img = Image.new("RGB", (w, h), "white")
    draw = ImageDraw.Draw(img)
    cx, cy = dot_xy
    draw.ellipse(
        (cx - DOT_RADIUS, cy - DOT_RADIUS, cx + DOT_RADIUS, cy + DOT_RADIUS),
        fill=DOT_COLOR,
    )
    img.save(out_path)


def parse_xy(text: str) -> tuple[float, float] | None:
    m = re.search(r"(-?\d+(?:\.\d+)?)\s*[,\s]\s*(-?\d+(?:\.\d+)?)", text)
    if not m:
        return None
    return float(m.group(1)), float(m.group(2))


def call_claude(model_id: str, image_path: Path, w: int, h: int, timeout: int) -> str:
    claude = resolve_cmd("claude")
    prompt = PROMPT.format(w=w, h=h) + f"\n\nImage: @{image_path}"
    proc = subprocess.run(
        [
            claude, "--print",
            "--model", model_id,
            "--add-dir", str(image_path.parent),
            "--disable-slash-commands",
            "--dangerously-skip-permissions",
        ],
        input=prompt,
        capture_output=True, text=True, timeout=timeout,
    )
    return proc.stdout.strip() if proc.returncode == 0 else f"ERR:{proc.stderr.strip()[:200]}"


def call_gemini(model_id: str, image_path: Path, w: int, h: int, timeout: int) -> str:
    """Use the gemini CLI in headless mode. Image is passed via @path
    reference in the prompt (CLI auto-attaches it)."""
    gemini = resolve_cmd("gemini")
    prompt = PROMPT.format(w=w, h=h) + f"\n\n@{image_path}"
    proc = subprocess.run(
        [
            gemini, "-y", "--skip-trust",
            "-m", model_id,
            "-p", prompt,
        ],
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=timeout,
    )
    out = proc.stdout.strip()
    # gemini prints warnings/banners to stderr; clean stdout is the answer.
    if not out:
        return f"ERR:{proc.stderr.strip()[:200]}"
    return out


# Gemini's vision processes images at 768x768 tiles. For square inputs,
# 768x768 is the natural size (no internal rescale).
GEMINI_SQUARE_SIDE = 768


def call_codex(model_id: str, image_path: Path, w: int, h: int, timeout: int) -> str:
    codex = resolve_cmd("codex")
    prompt = PROMPT.format(w=w, h=h)
    # codex writes the response to stderr (banner + reply + tokens used).
    # stdout is the final reply only when --json isn't used.
    # `-i FILE...` is variadic, so PROMPT must come first as positional.
    # Use "default" model from user's config (no -m) when model_id == "default".
    args = [codex, "exec", "--skip-git-repo-check"]
    if model_id and model_id != "default":
        args += ["-m", model_id]
    args += [prompt, "-i", str(image_path)]
    proc = subprocess.run(
        args,
        stdin=subprocess.DEVNULL,
        capture_output=True, text=True, timeout=timeout,
    )
    text = proc.stdout.strip() or proc.stderr
    # Find the final reply (between "codex\n" marker and "tokens used")
    m = re.search(r"\ncodex\n(.+?)\ntokens used", text, re.DOTALL)
    if m:
        return m.group(1).strip()
    # If we got an error, surface it
    err_m = re.search(r"ERROR:.+", text)
    if err_m:
        return f"ERR:{err_m.group(0)[:200]}"
    return f"ERR:{text.strip()[:200]}"


def positions_for(w: int, h: int, n: int) -> list[tuple[int, int]]:
    margin = max(DOT_RADIUS + 4, 30)
    candidates = [
        (margin, margin),
        (w - margin, margin),
        (margin, h - margin),
        (w - margin, h - margin),
        (w // 2, h // 2),
        (w // 3, 2 * h // 3),
        (2 * w // 3, h // 3),
    ]
    return [(int(c[0]), int(c[1])) for c in candidates[:n]]


def run(rows: list[dict], provider: str, model_short: str, model_id: str,
        side: int, positions: list[tuple[int, int]], out_dir: Path,
        timeout: int):
    for idx, (gx, gy) in enumerate(positions):
        # Neutral filename — the dot position must NOT appear in the path,
        # since call_claude/gemini pass "@{image_path}" as prompt text and the
        # model could read the answer straight out of the filename.
        img_path = out_dir / f"{provider}_{model_short}_{side}_{idx}.png"
        generate_image(img_path, side, side, (gx, gy))
        t0 = time.time()
        try:
            if provider == "claude":
                raw = call_claude(model_id, img_path, side, side, timeout)
            elif provider == "gemini":
                raw = call_gemini(model_id, img_path, side, side, timeout)
            else:
                raw = call_codex(model_id, img_path, side, side, timeout)
            pred = parse_xy(raw)
            err = (
                None if pred is None
                else math.hypot(pred[0] - gx, pred[1] - gy)
            )
        except subprocess.TimeoutExpired:
            raw, pred, err = "TIMEOUT", None, None
        except Exception as e:
            raw, pred, err = f"EXC:{e!r}"[:200], None, None
        rows.append({
            "provider": provider,
            "model": model_short,
            "model_id": model_id,
            "size": side,
            "expected": (gx, gy),
            "predicted": pred,
            "error_px": err,
            "elapsed_s": round(time.time() - t0, 1),
            "raw": raw[:100],
        })
        print(rows[-1], flush=True)


def format_report(rows: list[dict]) -> str:
    lines = []
    header = (
        f"{'prov':<6} {'model':<10} {'size':>5} {'expected':>10} "
        f"{'predicted':>12} {'err_px':>7} {'s':>4}  raw"
    )
    lines.append(header)
    lines.append("-" * len(header))
    for r in rows:
        exp = f"{r['expected'][0]},{r['expected'][1]}"
        pred = (
            f"{r['predicted'][0]:.0f},{r['predicted'][1]:.0f}"
            if r["predicted"] else "—"
        )
        err = f"{r['error_px']:.1f}" if r["error_px"] is not None else "—"
        raw = (r["raw"] or "").replace("\n", " ")[:60]
        lines.append(
            f"{r['provider']:<6} {r['model']:<10} {r['size']:>5} {exp:>10} "
            f"{pred:>12} {err:>7} {r['elapsed_s']:>4}  {raw}"
        )
    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--claude-models", default="opus-4.7,sonnet,haiku")
    parser.add_argument("--codex-models", default="default")
    parser.add_argument(
        "--gemini-models",
        default="",
        help="comma-separated gemini model IDs (e.g. gemini-2.5-flash,gemini-2.5-pro)",
    )
    parser.add_argument("--positions", type=int, default=3)
    parser.add_argument(
        "--out-dir",
        type=Path,
        default=Path(__file__).parent / "_validate_out",
    )
    parser.add_argument("--timeout", type=int, default=90)
    args = parser.parse_args()

    args.out_dir.mkdir(parents=True, exist_ok=True)
    rows: list[dict] = []

    for m in [x.strip() for x in args.claude_models.split(",") if x.strip()]:
        if m not in CLAUDE_MODEL_MAP:
            print(f"skip unknown claude model: {m}", file=sys.stderr)
            continue
        cli_id, vp_key = CLAUDE_MODEL_MAP[m]
        side = safe_square_side(vp_key)
        positions = positions_for(side, side, args.positions)
        print(f"\n=== claude {m} ({cli_id}) — {side}x{side} ===", flush=True)
        run(rows, "claude", m, cli_id, side, positions, args.out_dir, args.timeout)

    for m in [x.strip() for x in args.codex_models.split(",") if x.strip()]:
        # OpenAI processes square inputs at 768x768 natively (detail:high)
        side = OPENAI_SQUARE_SIDE
        positions = positions_for(side, side, args.positions)
        print(f"\n=== codex {m} — {side}x{side} ===", flush=True)
        run(rows, "codex", m, m, side, positions, args.out_dir, args.timeout)

    for m in [x.strip() for x in args.gemini_models.split(",") if x.strip()]:
        side = GEMINI_SQUARE_SIDE
        positions = positions_for(side, side, args.positions)
        print(f"\n=== gemini {m} — {side}x{side} ===", flush=True)
        run(rows, "gemini", m, m, side, positions, args.out_dir, args.timeout)

    print("\n" + format_report(rows))
    (args.out_dir / "results.json").write_text(json.dumps(rows, indent=2, default=str))
    print(f"\nFull results: {args.out_dir / 'results.json'}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
