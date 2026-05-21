"""Tests for tools/info.py"""
import json
import subprocess
import sys
from PIL import Image


def run_info(image_path):
    result = subprocess.run(
        [sys.executable, "tools/info.py", str(image_path)],
        capture_output=True, text=True,
    )
    assert result.returncode == 0, result.stderr
    return json.loads(result.stdout)


def test_info_landscape_small(sample_image):
    """200x100 sample image — vision-safe (landscape, ≤1568)."""
    data = run_info(sample_image)
    assert data["width"] == 200
    assert data["height"] == 100
    assert data["aspect"] == "2:1"
    assert data["format"] == "PNG"
    assert data["mode"] == "RGB"
    assert data["vision_safe"] is True
    assert data["size_bytes"] > 0


def test_info_large_not_vision_safe(large_image):
    """2000x1500 — long edge >1568 → not vision_safe."""
    data = run_info(large_image)
    assert data["width"] == 2000
    assert data["height"] == 1500
    assert data["vision_safe"] is False


def test_info_portrait_not_vision_safe(portrait_image):
    """600x900 — portrait → not vision_safe even though long edge ≤1568."""
    data = run_info(portrait_image)
    assert data["width"] == 600
    assert data["height"] == 900
    assert data["vision_safe"] is False


def test_info_square_is_vision_safe(tmp_dir):
    img = Image.new("RGB", (500, 500), "white")
    p = tmp_dir / "sq.png"
    img.save(p)
    data = run_info(p)
    assert data["vision_safe"] is True
    assert data["aspect"] == "1:1"


def test_info_path_in_output(sample_image):
    data = run_info(sample_image)
    assert data["path"] == str(sample_image)
