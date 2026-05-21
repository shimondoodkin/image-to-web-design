"""Tests for tools/resize.py"""
import json
import subprocess
import sys
from PIL import Image


def run_resize(args):
    return subprocess.run(
        [sys.executable, "tools/resize.py", *args],
        capture_output=True, text=True,
    )


def test_resize_fit_width(sample_image, tmp_dir):
    """200x100 → fit-width 100 → 100x50."""
    out = tmp_dir / "out.png"
    r = run_resize([str(sample_image), "--fit-width", "100", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    assert img.size == (100, 50)


def test_resize_fit_height(sample_image, tmp_dir):
    """200x100 → fit-height 50 → 100x50."""
    out = tmp_dir / "out.png"
    r = run_resize([str(sample_image), "--fit-height", "50", "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.size == (100, 50)


def test_resize_explicit_width_and_height(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_resize([
        str(sample_image), "--width", "300", "--height", "150",
        "--out", str(out),
    ])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.size == (300, 150)


def test_resize_scale(sample_image, tmp_dir):
    """200x100 → scale 0.5 → 100x50."""
    out = tmp_dir / "out.png"
    r = run_resize([str(sample_image), "--scale", "0.5", "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.size == (100, 50)


def test_resize_requires_a_mode(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_resize([str(sample_image), "--out", str(out)])
    assert r.returncode != 0


def test_resize_modes_mutually_exclusive(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_resize([
        str(sample_image), "--fit-width", "100", "--scale", "0.5",
        "--out", str(out),
    ])
    assert r.returncode != 0


def test_resize_width_without_height_errors(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_resize([str(sample_image), "--width", "300", "--out", str(out)])
    assert r.returncode != 0
    r = run_resize([str(sample_image), "--height", "150", "--out", str(out)])
    assert r.returncode != 0


def test_resize_receipt_fit_width(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_resize([str(sample_image), "--fit-width", "100", "--out", str(out)])
    assert r.returncode == 0
    data = json.loads((tmp_dir / "out.png.json").read_text())
    assert data["op"]["op"] == "resize"
    assert data["op"]["mode"] == "fit-width"
    assert data["op"]["in_size"] == [200, 100]
    assert data["op"]["out_size"] == [100, 50]


def test_resize_receipt_scale(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_resize([str(sample_image), "--scale", "0.5", "--out", str(out)])
    assert r.returncode == 0
    data = json.loads((tmp_dir / "out.png.json").read_text())
    assert data["op"]["mode"] == "scale"
