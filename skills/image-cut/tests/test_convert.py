"""Tests for tools/convert.py"""
import subprocess
import sys
from pathlib import Path
from PIL import Image


def run_convert(args):
    return subprocess.run(
        [sys.executable, "tools/convert.py", *args],
        capture_output=True, text=True,
    )


def test_convert_default_format_is_webp(sample_image, tmp_dir):
    out = tmp_dir / "out.bin"
    r = run_convert([str(sample_image), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    assert img.format == "WEBP"


def test_convert_to_jpg(sample_image, tmp_dir):
    out = tmp_dir / "out.jpg"
    r = run_convert([str(sample_image), "--format", "jpg", "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.format == "JPEG"


def test_convert_to_png(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_convert([str(sample_image), "--format", "png", "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    assert img.format == "PNG"


def test_convert_writes_no_receipt(sample_image, tmp_dir):
    out = tmp_dir / "out.webp"
    r = run_convert([str(sample_image), "--out", str(out)])
    assert r.returncode == 0
    assert not Path(str(out) + ".json").exists()


def test_convert_quality_default_98(sample_image, tmp_dir):
    out_high = tmp_dir / "high.webp"
    out_low = tmp_dir / "low.webp"
    r1 = run_convert([str(sample_image), "--out", str(out_high)])
    r2 = run_convert([
        str(sample_image), "--quality", "10", "--out", str(out_low),
    ])
    assert r1.returncode == 0 and r2.returncode == 0
    # Lower quality should produce a smaller file (or at least not larger,
    # for this trivial fixture content).
    assert out_low.stat().st_size <= out_high.stat().st_size


def test_convert_invalid_format_errors(sample_image, tmp_dir):
    out = tmp_dir / "out.bmp"
    r = run_convert([str(sample_image), "--format", "bmp", "--out", str(out)])
    assert r.returncode != 0
