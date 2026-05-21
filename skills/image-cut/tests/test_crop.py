"""Tests for tools/crop.py"""
import json
import subprocess
import sys
from PIL import Image


def run_crop(args):
    result = subprocess.run(
        [sys.executable, "tools/crop.py", *args],
        capture_output=True, text=True,
    )
    return result


def test_crop_basic(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_crop([str(sample_image), "--bbox", "0,0,100,50", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    assert out.exists()
    img = Image.open(out)
    assert img.size == (100, 50)


def test_crop_writes_receipt_sidecar(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_crop([str(sample_image), "--bbox", "10,20,110,80", "--out", str(out)])
    assert r.returncode == 0
    sidecar = tmp_dir / "out.png.json"
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["op"]["op"] == "crop"
    assert data["op"]["bbox"] == [10, 20, 110, 80]
    assert data["input"]["size"] == [200, 100]
    assert data["output"]["size"] == [100, 60]


def test_crop_echoes_receipt_to_stdout(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_crop([str(sample_image), "--bbox", "0,0,50,50", "--out", str(out)])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["op"]["op"] == "crop"


def test_crop_bbox_outside_image_errors(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_crop([str(sample_image), "--bbox", "0,0,500,500", "--out", str(out)])
    assert r.returncode != 0
    assert "bbox" in r.stderr.lower() or "bounds" in r.stderr.lower()


def test_crop_negative_bbox_errors(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_crop([str(sample_image), "--bbox", "-5,0,50,50", "--out", str(out)])
    assert r.returncode != 0


def test_crop_inverted_bbox_errors(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_crop([str(sample_image), "--bbox", "100,50,50,25", "--out", str(out)])
    assert r.returncode != 0


def test_crop_webp_output_default_quality(sample_image, tmp_dir):
    out = tmp_dir / "out.webp"
    r = run_crop([str(sample_image), "--bbox", "0,0,100,50", "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.format == "WEBP"


def test_crop_preserves_pixel_content(sample_image, tmp_dir):
    """Crop (50, 25, 51, 26) should give a 1x1 image of the green pixel."""
    out = tmp_dir / "px.png"
    r = run_crop([str(sample_image), "--bbox", "50,25,51,26", "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.getpixel((0, 0)) == (0, 255, 0)
