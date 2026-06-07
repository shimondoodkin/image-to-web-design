#!/usr/bin/env python3
"""Single-file, zero-config image prep for Claude vision coordinate work.

Bakes in the settled configuration from the 2026-06-07 coordinate-accuracy
study (docs/research/2026-06-07-opus48-coordinate-accuracy.md). You pass an
image and an output path — nothing to tune.

What it does, and why (all measured):
  1. Downscale so the long edge <= 768 px. 768 is the sweet spot: ~1px corner
     error, and large coordinates (>~1000) make the model bimodal/unreliable.
  2. Pad tiny inputs UP to a 768 canvas. Native images <~200px hallucinate;
     padding the canvas up fixes them while keeping content sharp.
  3. Add a 50px white margin on the right/bottom. A target jammed against the
     edge loses ~8px to the corner dead-zone; 50px restores ~0.3px.

Content is always pasted at (0,0), so detected coordinates map straight back to
the ORIGINAL image with no offset — just divide by `scale` (in the receipt)
when a large input was downscaled. For fine precision on a large source, crop
the region of interest first and prep that (keeps the target at small coords).

Usage:
  prep_claude.py INPUT --out PATH [--model opus-4.8]

--model is informational (recorded in the receipt): at a 768 long edge every
Claude model processes the image unscaled, so it does not affect sizing.
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image, ImageFilter

# ── settled constants (see the research report) ──────────────────────────────
TARGET_EDGE = 768   # downscale ceiling AND minimum canvas edge (the sweet spot)
EDGE_MARGIN = 50    # white margin on right/bottom (corner dead-zone mitigation)
JPEG_QUALITY = 98


def save_image_with_quality(img: Image.Image, out_path: Path) -> None:
    ext = out_path.suffix.lower().lstrip(".")
    kw: dict[str, Any] = {}
    if ext in {"jpg", "jpeg"}:
        kw["quality"] = JPEG_QUALITY
        if img.mode in {"RGBA", "LA", "P"}:
            img = img.convert("RGB")
    elif ext == "webp":
        kw["quality"] = JPEG_QUALITY
    img.save(out_path, **kw)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Zero-config image prep for Claude vision coordinates."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--out", type=Path, required=True)
    parser.add_argument("--model", default="opus-4.8",
                        help="recorded in the receipt; does not affect sizing.")
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    with Image.open(args.input) as orig:
        in_w, in_h = orig.size
        img = orig.convert("RGB") if orig.mode not in {"RGB", "RGBA"} else orig.copy()

        # 1. Downscale so the long edge <= TARGET_EDGE (never upscales).
        scale = min(1.0, TARGET_EDGE / max(in_w, in_h))
        if scale < 1.0:
            sc_w = max(1, round(in_w * scale))
            sc_h = max(1, round(in_h * scale))
            content = img.resize((sc_w, sc_h), Image.Resampling.LANCZOS)
            content = content.filter(
                ImageFilter.UnsharpMask(radius=1, percent=80, threshold=0)
            )
        else:
            sc_w, sc_h = in_w, in_h
            content = img

        # 2 + 3. Emit on a white canvas: content at (0,0), with at least
        # EDGE_MARGIN of margin on right/bottom AND each edge >= TARGET_EDGE
        # (pads tiny inputs up). Right/bottom only -> coords need no offset.
        out_w = max(sc_w + EDGE_MARGIN, TARGET_EDGE)
        out_h = max(sc_h + EDGE_MARGIN, TARGET_EDGE)
        if (out_w, out_h) != (sc_w, sc_h):
            white = (255, 255, 255, 255) if content.mode == "RGBA" else (255, 255, 255)
            out_img = Image.new(content.mode, (out_w, out_h), white)
            out_img.paste(content, (0, 0))
        else:
            out_img = content

        save_image_with_quality(out_img, args.out)

    receipt = {
        "input": {"path": str(args.input), "size": [in_w, in_h]},
        "output": {"path": str(args.out), "size": [out_w, out_h]},
        "op": {
            "op": "prep_claude",
            "model": args.model,
            "scale": scale,
            "content_size": [sc_w, sc_h],
            "emitted_size": [out_w, out_h],
            "target_edge": TARGET_EDGE,
            "edge_margin": EDGE_MARGIN,
        },
    }
    Path(str(args.out) + ".json").write_text(json.dumps(receipt))
    print(json.dumps(receipt))
    return 0


if __name__ == "__main__":
    sys.exit(main())
