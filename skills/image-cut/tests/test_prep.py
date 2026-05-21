"""Tests for tools/prep.py (high-level wrapper: crop + pad + vision_prep)."""
import subprocess
import sys
from PIL import Image


PAD_MULTIPLE = 28


def run_prep(args):
    return subprocess.run(
        [sys.executable, "tools/prep.py", *args],
        capture_output=True, text=True,
    )


def test_prep_no_region_uses_whole_image(sample_image, tmp_dir):
    """No region, no scaling needed (sample is small) → native size."""
    out = tmp_dir / "out.png"
    r = run_prep([str(sample_image), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    # sample is 200x100, well under cap → emitted at native size
    assert img.size == (200, 100)


def test_prep_with_region(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_prep([
        str(sample_image), "--region", "10,20,110,80",
        "--out", str(out),
    ])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    # 100x60 region, well under cap → emitted at native size
    assert img.size == (100, 60)


def test_prep_with_padding(sample_image, tmp_dir):
    """Padding is added around the region before vision_prep."""
    out = tmp_dir / "out.png"
    r = run_prep([
        str(sample_image), "--region", "10,20,110,80",
        "--pad-top", "5", "--pad-right", "5",
        "--pad-bottom", "5", "--pad-left", "5",
        "--out", str(out),
    ])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    # 100x60 + 10/10 pad = 110x70, under cap → emitted at 110x70
    assert img.size == (110, 70)


def test_prep_origin_aligned_with_region(sample_image, tmp_dir):
    """Top-left pixel of prep output = top-left of region (no offset)."""
    out = tmp_dir / "out.png"
    r = run_prep([
        str(sample_image), "--region", "50,25,150,75",
        "--out", str(out),
    ])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    # Green pixel was at (50, 25) in sample, so it lands at (0, 0) of region.
    assert img.getpixel((0, 0)) == (0, 255, 0)


def test_prep_invalid_region_errors(sample_image, tmp_dir):
    out = tmp_dir / "out.png"
    r = run_prep([
        str(sample_image), "--region", "0,0,500,500",
        "--out", str(out),
    ])
    assert r.returncode != 0


def test_prep_full_image_with_padding(sample_image, tmp_dir):
    """No region, but padding still works (pads the whole image)."""
    out = tmp_dir / "out.png"
    r = run_prep([
        str(sample_image),
        "--pad-right", "20", "--pad-bottom", "10",
        "--out", str(out),
    ])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    # sample 200x100 + agent pad 20/10 = 220x110, under cap → native size
    assert img.size == (220, 110)


def test_prep_model_opus_47_allows_larger(tmp_dir):
    """Same large input → opus-4.7 keeps more pixels than sonnet."""
    big = tmp_dir / "big.png"
    Image.new("RGB", (2000, 1500), "white").save(big)

    out_sonnet = tmp_dir / "sonnet.png"
    out_opus = tmp_dir / "opus.png"
    r1 = run_prep([str(big), "--model", "sonnet", "--out", str(out_sonnet)])
    r2 = run_prep([str(big), "--model", "opus-4.7", "--out", str(out_opus)])
    assert r1.returncode == 0 and r2.returncode == 0
    s = Image.open(out_sonnet).size
    o = Image.open(out_opus).size
    assert o[0] * o[1] > s[0] * s[1]
