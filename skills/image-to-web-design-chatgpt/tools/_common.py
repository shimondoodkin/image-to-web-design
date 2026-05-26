"""Shared helpers for image-to-web-design-chatgpt tools."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any
from PIL import Image


def write_receipt(
    out_path: Path,
    input_path: Path,
    input_size: tuple[int, int],
    output_size: tuple[int, int],
    op: dict[str, Any],
) -> dict[str, Any]:
    """Write a sidecar receipt at <out_path>.json and echo to stdout.

    Returns the receipt dict.
    """
    receipt = {
        "input": {"path": str(input_path), "size": list(input_size)},
        "output": {"path": str(out_path), "size": list(output_size)},
        "op": op,
    }
    sidecar = Path(str(out_path) + ".json")
    sidecar.write_text(json.dumps(receipt))
    print(json.dumps(receipt), file=sys.stdout)
    return receipt


def parse_hex_color(s: str) -> tuple[int, int, int]:
    """Parse a 3- or 6-digit hex color string into an (r, g, b) tuple."""
    s = s.lstrip("#")
    if len(s) == 3:
        try:
            return tuple(int(c * 2, 16) for c in s)  # type: ignore[return-value]
        except ValueError as e:
            raise ValueError(f"invalid hex color: #{s}") from e
    if len(s) == 6:
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError as e:
            raise ValueError(f"invalid hex color: #{s}") from e
    raise ValueError(f"invalid hex color: #{s} (must be 3 or 6 hex digits)")


def save_image_with_quality(img: Image.Image, out_path: Path, quality: int) -> None:
    """Save image, applying quality only to jpg/webp."""
    ext = out_path.suffix.lower().lstrip(".")
    save_kwargs: dict[str, Any] = {}
    if ext in {"jpg", "jpeg"}:
        save_kwargs["quality"] = quality
        if img.mode in {"RGBA", "LA", "P"}:
            img = img.convert("RGB")
    elif ext == "webp":
        save_kwargs["quality"] = quality
    img.save(out_path, **save_kwargs)
