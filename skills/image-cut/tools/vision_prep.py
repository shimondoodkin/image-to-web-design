#!/usr/bin/env python3
"""Pre-scale + pad an image to match each vendor's vision pipeline exactly.

Different vendors process images differently. This tool mirrors the relevant
pipeline client-side so what we send is exactly what the model processes —
no internal rescaling, accurate coordinate translation.

## Claude family (sonnet / opus-4.6 / opus-4.7 / haiku)

  1. Resize to fit (max_long_edge, max_tokens), preserving aspect.
  2. Pad bottom/right to multiple of 28 pixels.

  Model         max long edge   max tokens
  sonnet,                1568         1568
  opus-4.6,              1568         1568
  haiku                  1568         1568
  opus-4.7               2576         4784

  Token formula: width * height / 750.

## Gemini family (gemini-3-flash, gemini-2.5-pro, etc.)

  Pricing-aware tile selection:
  - If both dims ≤ 384: 258 tokens flat, no rescale/pad needed.
  - Else: cheapest N×M arrangement of 768x768 tiles (N,M ∈ 1..3) that
    contains the image at scale=1. Cost = N*M*258 tokens.
  - If image exceeds 3x3 tiles (2304x2304): downscale to fit 3x3.

Usage:
  vision_prep.py INPUT [--model sonnet|opus-4.6|opus-4.7|haiku|
                                gemini-3-flash|gemini-3.1-pro|...]
                       [--color #000000] [--quality N=98]
                       --out PATH
"""
from __future__ import annotations
import argparse
import math
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageFilter
from _common import write_receipt, parse_hex_color, save_image_with_quality  # noqa: E402


CLAUDE_PAD_MULTIPLE = 28
GEMINI_TILE = 768
GEMINI_SMALL_MAX = 384


MODEL_LIMITS: dict[str, dict] = {
    # Claude family
    "sonnet": {"family": "claude", "max_long_edge": 1568, "max_tokens": 1568},
    "opus-4.6": {"family": "claude", "max_long_edge": 1568, "max_tokens": 1568},
    "haiku": {"family": "claude", "max_long_edge": 1568, "max_tokens": 1568},
    "opus-4.7": {"family": "claude", "max_long_edge": 2576, "max_tokens": 4784},
    # Gemini family — all models use the same tile-based pipeline
    "gemini-3-flash": {"family": "gemini"},
    "gemini-3-flash-preview": {"family": "gemini"},
    "gemini-3.1-pro": {"family": "gemini"},
    "gemini-3.1-pro-preview": {"family": "gemini"},
    "gemini-3.1-flash-lite": {"family": "gemini"},
    "gemini-3.1-flash-lite-preview": {"family": "gemini"},
    "gemini-2.5-pro": {"family": "gemini"},
    "gemini-2.5-flash": {"family": "gemini"},
    "gemini-2.5-flash-lite": {"family": "gemini"},
}


def _compute_claude_target(in_w: int, in_h: int, config: dict):
    """Scale (downscale-only) so the image fits both Claude caps:
    max_long_edge and max_tokens.

    No multiple-of-28 padding: that's a billing/tile concept, not a
    sizing one. As long as the image we send is under the cap, Claude
    won't internally rescale, and coords come back accurate. We use
    floor + verification to ensure we stay strictly under the token cap
    (rounding could push us 1 pixel over for borderline cases).
    """
    max_long_edge = config["max_long_edge"]
    max_tokens = config["max_tokens"]
    max_pixels = max_tokens * 750

    long_edge_scale = max_long_edge / max(in_w, in_h)
    token_scale = math.sqrt(max_pixels / (in_w * in_h))
    scale = min(1.0, long_edge_scale, token_scale)

    scaled_w = max(1, math.floor(in_w * scale))
    scaled_h = max(1, math.floor(in_h * scale))
    # Verify token cap (floor + verify handles float rounding at the edge).
    while scaled_w * scaled_h > max_pixels and (scaled_w > 1 or scaled_h > 1):
        if scaled_w >= scaled_h:
            scaled_w -= 1
        else:
            scaled_h -= 1

    return scale, (scaled_w, scaled_h), (scaled_w, scaled_h)


def _compute_gemini_target(in_w: int, in_h: int):
    """Gemini accepts any image size at full accuracy — no padding needed.

    The output is the image at native size (if it fits within the 3×3 grid
    of 768x768 tiles) or downscaled to fit. Google charges based on tile
    arrangement regardless of whether the file is padded, so padding only
    bloats the file.
    """
    max_dim = 3 * GEMINI_TILE  # 2304
    if in_w <= max_dim and in_h <= max_dim:
        # Fits at native size
        return 1.0, (in_w, in_h), (in_w, in_h)
    # Bigger than 3×3 grid: downscale to fit. No padding.
    scale = min(max_dim / in_w, max_dim / in_h)
    scaled_w = max(1, round(in_w * scale))
    scaled_h = max(1, round(in_h * scale))
    return scale, (scaled_w, scaled_h), (scaled_w, scaled_h)


def compute_target(in_w: int, in_h: int, model: str) -> tuple[float, tuple[int, int], tuple[int, int]]:
    """Return (scale, scaled_size, padded_size) for the given model.

    - scale: factor applied to input dims (≤1.0, never upscales)
    - scaled_size: dims after scale, before padding
    - padded_size: final output dims (the size we actually emit)
    """
    config = MODEL_LIMITS[model]
    family = config["family"]
    if family == "claude":
        return _compute_claude_target(in_w, in_h, config)
    if family == "gemini":
        return _compute_gemini_target(in_w, in_h)
    raise ValueError(f"unknown vision family: {family}")


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-scale + pad an image to match the model's vision pipeline."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--model",
        choices=list(MODEL_LIMITS.keys()),
        default="sonnet",
    )
    parser.add_argument("--color", default="#000000")
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    try:
        color_rgb = parse_hex_color(args.color)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    with Image.open(args.input) as img:
        in_w, in_h = img.size
        if img.mode not in {"RGB", "RGBA"}:
            img = img.convert("RGB")

        scale, (scaled_w, scaled_h), (padded_w, padded_h) = compute_target(
            in_w, in_h, args.model
        )

        if scale < 1.0:
            resized = img.resize((scaled_w, scaled_h), Image.Resampling.LANCZOS)
            resized = resized.filter(
                ImageFilter.UnsharpMask(radius=1, percent=80, threshold=0)
            )
        else:
            resized = img

        if (padded_w, padded_h) != (scaled_w, scaled_h):
            fill = (*color_rgb, 255) if resized.mode == "RGBA" else color_rgb
            canvas = Image.new(resized.mode, (padded_w, padded_h), fill)
            canvas.paste(resized, (0, 0))
            out_img = canvas
        else:
            out_img = resized
        save_image_with_quality(out_img, args.out, args.quality)

    color_hex = "#{:02x}{:02x}{:02x}".format(*color_rgb)
    write_receipt(
        out_path=args.out,
        input_path=args.input,
        input_size=(in_w, in_h),
        output_size=(padded_w, padded_h),
        op={
            "op": "vision_prep",
            "model": args.model,
            "family": MODEL_LIMITS[args.model]["family"],
            "scale": scale,
            "scaled_size": [scaled_w, scaled_h],
            "padded_size": [padded_w, padded_h],
            "color": color_hex,
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
