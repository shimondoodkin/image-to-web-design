"""Tests for tools/pad.py"""
import json
import subprocess
import sys
from PIL import Image


def run_pad(args):
    return subprocess.run(
        [sys.executable, "tools/pad.py", *args],
        capture_output=True, text=True,
    )


def test_pad_all_sides(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_pad([
        str(sample_image),
        "--pad-top", "10", "--pad-right", "20",
        "--pad-bottom", "30", "--pad-left", "40",
        "--out", str(out),
    ])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    # original 200x100, pad: top=10, right=20, bottom=30, left=40
    # → new size (200+40+20, 100+10+30) = (260, 140)
    assert img.size == (260, 140)


def test_pad_single_side(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_pad([str(sample_image), "--pad-left", "50", "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.size == (250, 100)


def test_pad_requires_at_least_one_pad(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_pad([str(sample_image), "--out", str(out)])
    assert r.returncode != 0


def test_pad_color_black_default(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_pad([str(sample_image), "--pad-left", "10", "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.getpixel((0, 0)) == (0, 0, 0)


def test_pad_color_custom(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_pad([
        str(sample_image), "--pad-left", "10",
        "--color", "#ff8040", "--out", str(out),
    ])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.getpixel((0, 0)) == (255, 128, 64)


def test_pad_receipt(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_pad([
        str(sample_image), "--pad-top", "10", "--pad-left", "20",
        "--out", str(out),
    ])
    assert r.returncode == 0
    data = json.loads((tmp_dir / "out.png.json").read_text())
    assert data["op"]["op"] == "pad"
    assert data["op"]["pad"] == {"top": 10, "right": 0, "bottom": 0, "left": 20}
    assert data["op"]["color"] == "#000000"
    assert data["output"]["size"] == [220, 110]


def test_pad_preserves_original_pixels(sample_image, tmp_dir):
    """Green pixel at (50, 25) should land at (50+left, 25+top)."""
    out = tmp_dir / "out.png"
    r = run_pad([
        str(sample_image), "--pad-top", "5", "--pad-left", "7",
        "--out", str(out),
    ])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.getpixel((57, 30)) == (0, 255, 0)
