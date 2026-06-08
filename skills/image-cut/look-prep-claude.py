#!/usr/bin/env python3
"""
Prepare an image for Claude vision coordinate work.

The script does three things:

1. Shrinks large images so the longest edge is at most 768 px.
2. Pads small images onto a 768 x 768 or larger white canvas.
3. Adds a 50 px white margin on the right and bottom.

The image content is always placed at position (0, 0).
That means Claude's detected coordinates map back to the original image like this:

    original_x = detected_x / scale
    original_y = detected_y / scale

Usage:

    look-prep-claude.py input.png --output output.jpg
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path

from PIL import Image, ImageFilter


TARGET_EDGE = 768
EDGE_MARGIN = 50
JPEG_QUALITY = 98


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Prepare an image for Claude vision coordinate work."
    )

    parser.add_argument("input", type=Path, help="Input image path")
    parser.add_argument("--output", type=Path, required=True, help="Output image path")

    return parser.parse_args()


def load_image(path: Path) -> Image.Image:
    image = Image.open(path)

    if image.mode not in {"RGB", "RGBA"}:
        image = image.convert("RGB")
    else:
        image = image.copy()

    return image


def calculate_scale(width: int, height: int) -> float:
    longest_edge = max(width, height)
    return min(1.0, TARGET_EDGE / longest_edge)


def resize_if_needed(image: Image.Image, scale: float) -> Image.Image:
    if scale >= 1.0:
        return image

    width, height = image.size

    new_width = max(1, round(width * scale))
    new_height = max(1, round(height * scale))

    resized = image.resize(
        (new_width, new_height),
        Image.Resampling.LANCZOS,
    )

    return resized.filter(
        ImageFilter.UnsharpMask(radius=1, percent=80, threshold=0)
    )


def put_on_white_canvas(image: Image.Image) -> Image.Image:
    width, height = image.size

    canvas_width = max(width + EDGE_MARGIN, TARGET_EDGE)
    canvas_height = max(height + EDGE_MARGIN, TARGET_EDGE)

    if (canvas_width, canvas_height) == image.size:
        return image

    background_color = (
        (255, 255, 255, 255)
        if image.mode == "RGBA"
        else (255, 255, 255)
    )

    canvas = Image.new(image.mode, (canvas_width, canvas_height), background_color)
    canvas.paste(image, (0, 0))

    return canvas


def save_image(image: Image.Image, path: Path) -> None:
    extension = path.suffix.lower().lstrip(".")
    options = {}

    if extension in {"jpg", "jpeg"}:
        options["quality"] = JPEG_QUALITY

        if image.mode in {"RGBA", "LA", "P"}:
            image = image.convert("RGB")

    elif extension == "webp":
        options["quality"] = JPEG_QUALITY

    image.save(path, **options)


def print_result(
    input_path: Path,
    input_size: tuple[int, int],
    output_path: Path,
    output_size: tuple[int, int],
    scale: float,
) -> None:
    result = {
        "input": {
            "path": str(input_path),
            "size": list(input_size),
        },
        "output": {
            "path": str(output_path),
            "size": list(output_size),
        },
        "scale": scale,
    }

    print(json.dumps(result, indent=2))


def main() -> int:
    args = parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    image = load_image(args.input)
    input_size = image.size

    scale = calculate_scale(*input_size)

    image = resize_if_needed(image, scale)
    image = put_on_white_canvas(image)

    save_image(image, args.output)

    print_result(
        input_path=args.input,
        input_size=input_size,
        output_path=args.output,
        output_size=image.size,
        scale=scale,
    )

    return 0


if __name__ == "__main__":
    sys.exit(main())