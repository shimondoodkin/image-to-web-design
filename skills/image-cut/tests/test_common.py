"""Tests for tools/_common.py shared helpers."""
import json
from pathlib import Path
import pytest
from tools._common import (
    write_receipt,
    parse_hex_color,
    save_image_with_quality,
)
from PIL import Image


def test_write_receipt_creates_sidecar_and_returns_json(tmp_path):
    out_path = tmp_path / "out.png"
    receipt = write_receipt(
        out_path=out_path,
        input_path=Path("in.png"),
        input_size=(100, 50),
        output_size=(80, 40),
        op={"op": "crop", "bbox": [10, 5, 90, 45]},
    )
    sidecar = tmp_path / "out.png.json"
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["input"]["path"] == "in.png"
    assert data["input"]["size"] == [100, 50]
    assert data["output"]["path"] == str(out_path)
    assert data["output"]["size"] == [80, 40]
    assert data["op"]["op"] == "crop"
    assert receipt == data


def test_parse_hex_color_three_digit():
    assert parse_hex_color("#000") == (0, 0, 0)
    assert parse_hex_color("#fff") == (255, 255, 255)
    assert parse_hex_color("#f0a") == (255, 0, 170)


def test_parse_hex_color_six_digit():
    assert parse_hex_color("#000000") == (0, 0, 0)
    assert parse_hex_color("#ffffff") == (255, 255, 255)
    assert parse_hex_color("#ff8040") == (255, 128, 64)


def test_parse_hex_color_without_hash():
    assert parse_hex_color("000000") == (0, 0, 0)


def test_parse_hex_color_invalid_raises():
    with pytest.raises(ValueError):
        parse_hex_color("not-a-color")
    with pytest.raises(ValueError):
        parse_hex_color("#12345")


def test_save_image_with_quality_jpg(tmp_path):
    img = Image.new("RGB", (10, 10), "red")
    out = tmp_path / "out.jpg"
    save_image_with_quality(img, out, quality=80)
    assert out.exists()
    reopened = Image.open(out)
    assert reopened.size == (10, 10)
    assert reopened.format == "JPEG"


def test_save_image_with_quality_webp(tmp_path):
    img = Image.new("RGB", (10, 10), "red")
    out = tmp_path / "out.webp"
    save_image_with_quality(img, out, quality=98)
    assert out.exists()


def test_save_image_with_quality_png_ignores_quality(tmp_path):
    img = Image.new("RGB", (10, 10), "red")
    out = tmp_path / "out.png"
    save_image_with_quality(img, out, quality=50)
    assert out.exists()
    reopened = Image.open(out)
    assert reopened.format == "PNG"
