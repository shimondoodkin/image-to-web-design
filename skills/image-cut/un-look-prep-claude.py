#!/usr/bin/env python3
"""
Convert Claude-detected coordinates back to the original image.

This is the reverse of look-prep-claude.py.

look-prep-claude.py may shrink the image, but it always places the image content
at position (0, 0). So the reverse mapping is simple:

    original_x = detected_x / scale
    original_y = detected_y / scale

The scale is recalculated from the original image size:

    scale = min(1, 768 / max(width, height))

Supported coordinate formats:

    [x, y]
    [x1, y1, x2, y2]
    [x1, y1, x2, y2, x3, y3, ...]
    {"x": 10, "y": 20}
    {"logo": [40, 30], "button": [700, 520, 760, 560]}
    nested lists and dictionaries

Usage:

    un-look-prep-claude.py --input-was original.png --coords '[384, 540]'
    un-look-prep-claude.py --input-was original.png -f detections.json
    echo '[[100,100],[700,500]]' | un-look-prep-claude.py --input-was original.png
"""

from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from PIL import Image


TARGET_EDGE = 768


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Convert Claude coordinates back to the original image."
    )

    parser.add_argument(
        "--input-was",
        type=Path,
        required=True,
        help="Original image that was passed to look-prep-claude.py",
    )

    parser.add_argument(
        "--coords",
        help="Inline JSON coordinates",
    )

    parser.add_argument(
        "-f",
        "--file",
        type=Path,
        help="JSON file containing coordinates",
    )

    parser.add_argument(
        "--out-json",
        type=Path,
        help="Optional path to write the converted JSON result",
    )

    parser.add_argument(
        "--float",
        action="store_true",
        help="Keep 2 decimal places instead of rounding to integers",
    )

    return parser.parse_args()


def get_image_size(path: Path) -> tuple[int, int]:
    with Image.open(path) as image:
        return image.size


def calculate_scale(width: int, height: int) -> float:
    longest_edge = max(width, height)
    return min(1.0, TARGET_EDGE / longest_edge)


def clamp(value: float, minimum: float, maximum: float) -> float:
    return min(max(value, minimum), maximum)


def convert_point(
    x: float,
    y: float,
    scale: float,
    image_width: int,
    image_height: int,
    keep_float: bool,
) -> tuple[int | float, int | float]:
    original_x = clamp(x / scale, 0.0, float(image_width))
    original_y = clamp(y / scale, 0.0, float(image_height))

    if keep_float:
        return round(original_x, 2), round(original_y, 2)

    return round(original_x), round(original_y)


def is_number(value: Any) -> bool:
    return isinstance(value, int | float)


def is_flat_coordinate_list(value: list[Any]) -> bool:
    return (
        len(value) > 0
        and len(value) % 2 == 0
        and all(is_number(item) for item in value)
    )


def convert_flat_coordinate_list(
    values: list[int | float],
    scale: float,
    image_width: int,
    image_height: int,
    keep_float: bool,
) -> list[int | float]:
    converted: list[int | float] = []

    for index in range(0, len(values), 2):
        x = values[index]
        y = values[index + 1]

        original_x, original_y = convert_point(
            x=x,
            y=y,
            scale=scale,
            image_width=image_width,
            image_height=image_height,
            keep_float=keep_float,
        )

        converted.extend([original_x, original_y])

    return converted


def convert_coordinates(
    value: Any,
    scale: float,
    image_width: int,
    image_height: int,
    keep_float: bool,
) -> Any:
    """
    Walk through any JSON-like structure and convert coordinate values.

    Converts:
    - dictionaries with x/y keys
    - flat even-length number lists
    - nested dictionaries and lists

    Leaves everything else unchanged.
    """

    if isinstance(value, dict):
        return convert_dict(
            value=value,
            scale=scale,
            image_width=image_width,
            image_height=image_height,
            keep_float=keep_float,
        )

    if isinstance(value, list):
        return convert_list(
            value=value,
            scale=scale,
            image_width=image_width,
            image_height=image_height,
            keep_float=keep_float,
        )

    return value


def convert_dict(
    value: dict[Any, Any],
    scale: float,
    image_width: int,
    image_height: int,
    keep_float: bool,
) -> dict[Any, Any]:
    converted = {
        key: convert_coordinates(
            value=item,
            scale=scale,
            image_width=image_width,
            image_height=image_height,
            keep_float=keep_float,
        )
        for key, item in value.items()
    }

    has_x_y = is_number(value.get("x")) and is_number(value.get("y"))

    if has_x_y:
        converted["x"], converted["y"] = convert_point(
            x=value["x"],
            y=value["y"],
            scale=scale,
            image_width=image_width,
            image_height=image_height,
            keep_float=keep_float,
        )

    return converted


def convert_list(
    value: list[Any],
    scale: float,
    image_width: int,
    image_height: int,
    keep_float: bool,
) -> list[Any]:
    if is_flat_coordinate_list(value):
        return convert_flat_coordinate_list(
            values=value,
            scale=scale,
            image_width=image_width,
            image_height=image_height,
            keep_float=keep_float,
        )

    return [
        convert_coordinates(
            value=item,
            scale=scale,
            image_width=image_width,
            image_height=image_height,
            keep_float=keep_float,
        )
        for item in value
    ]


def read_coordinates(args: argparse.Namespace) -> str:
    if args.coords is not None:
        return args.coords

    if args.file is not None:
        return args.file.read_text()

    return sys.stdin.read()


def load_json(raw_json: str) -> Any:
    if not raw_json.strip():
        raise ValueError("no coordinates given")

    return json.loads(raw_json)


def write_result(result: Any, output_path: Path | None) -> None:
    output_json = json.dumps(result)

    print(output_json)

    if output_path is not None:
        output_path.write_text(output_json)


def print_transform_info(scale: float, width: int, height: int) -> None:
    print(
        f"# transform: scale={scale:.6g} (x{1 / scale:.4g}) orig={width}x{height}",
        file=sys.stderr,
    )


def main() -> int:
    args = parse_args()

    try:
        image_width, image_height = get_image_size(args.input_was)
        scale = calculate_scale(image_width, image_height)

        raw_coordinates = read_coordinates(args)
        coordinates = load_json(raw_coordinates)

        result = convert_coordinates(
            value=coordinates,
            scale=scale,
            image_width=image_width,
            image_height=image_height,
            keep_float=args.float,
        )

        write_result(result, args.out_json)
        print_transform_info(scale, image_width, image_height)

        return 0

    except FileNotFoundError:
        print(f"error: input image not found: {args.input_was}", file=sys.stderr)
        return 2

    except json.JSONDecodeError as error:
        print(f"error: invalid JSON coordinates: {error}", file=sys.stderr)
        return 2

    except ValueError as error:
        print(f"error: {error}", file=sys.stderr)
        return 2


if __name__ == "__main__":
    sys.exit(main())