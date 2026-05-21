"""Tests for tools/points.py (high-level: translate looked-at points → original coords)."""
import json
import subprocess
import sys
from PIL import Image


def run_points(args):
    return subprocess.run(
        [sys.executable, "tools/points.py", *args],
        capture_output=True, text=True,
    )


def make_image(path, size, color="white"):
    Image.new("RGB", size, color).save(path)
    return path


def test_points_origin_with_region(sample_image, tmp_dir):
    """Point (0,0) in prep output = top-left of region in original."""
    r = run_points([
        str(sample_image), "--region", "50,25,150,75",
        "--points", "0,0", "--round",
    ])
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["points"] == [[50, 25]]


def test_points_origin_no_region(sample_image, tmp_dir):
    """Point (0,0) in prep output (no region) = (0,0) in original."""
    r = run_points([str(sample_image), "--points", "0,0", "--round"])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["points"] == [[0, 0]]


def test_points_batch_multiple(sample_image, tmp_dir):
    """Multiple points translated in one call."""
    r = run_points([
        str(sample_image), "--region", "50,25,150,75",
        "--points", "0,0;100,50",  # corners of the scaled region
        "--round",
    ])
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert len(data["points"]) == 2
    assert data["points"][0] == [50, 25]


def test_points_with_padding(sample_image, tmp_dir):
    """Padding shifts the source content within the prepped image.

    Region (50, 25, 150, 75) + pad-left 7, pad-top 5.
    Cropped region: 100x50 → padded: 107x55. Fits inside any tile at
    scale=1 (no upscaling), so prep coords = padded coords directly.
    The region's (50, 25) corner is at (7, 5) in the padded intermediate.
    Translating prep (7, 5) back should give original (50, 25).
    """
    r = run_points([
        str(sample_image), "--region", "50,25,150,75",
        "--pad-top", "5", "--pad-left", "7",
        "--points", "7,5",
        "--round",
    ])
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    gx, gy = data["points"][0]
    assert abs(gx - 50) <= 1
    assert abs(gy - 25) <= 1


def test_points_end_to_end_with_prep(tmp_dir):
    """Run prep, then translate a known prep-output coord back to original."""
    # Make a 1000x1000 screenshot with a marker block (LANCZOS blends single
    # pixels — use a block so the green survives resampling).
    orig = tmp_dir / "screen.png"
    img = Image.new("RGB", (1000, 1000), "white")
    for y in range(345, 355):
        for x in range(245, 255):
            img.putpixel((x, y), (0, 255, 0))
    img.save(orig)

    # Prep a region (200, 300, 800, 700) around the marker
    prep_out = tmp_dir / "prep.png"
    r = subprocess.run(
        [sys.executable, "tools/prep.py", str(orig),
         "--region", "200,300,800,700", "--out", str(prep_out)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr

    # Find a strongly-green pixel in prep output (dominant green channel)
    prep_img = Image.open(prep_out)
    green_in_prep = None
    for y in range(prep_img.height):
        for x in range(prep_img.width):
            px = prep_img.getpixel((x, y))
            if px[1] > 200 and px[0] < 100 and px[2] < 100:
                green_in_prep = (x, y)
                break
        if green_in_prep:
            break
    assert green_in_prep is not None, "green block not found in prep output"

    # Translate that prep coord back to original
    r = run_points([
        str(orig), "--region", "200,300,800,700",
        "--points", f"{green_in_prep[0]},{green_in_prep[1]}",
        "--round",
    ])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    gx, gy = data["points"][0]
    # Marker block was (245-254, 345-354) — translated point should land
    # inside the block, ±2 for resampling.
    assert 243 <= gx <= 256, f"expected 245-254, got {gx}"
    assert 343 <= gy <= 356, f"expected 345-354, got {gy}"


def test_points_requires_at_least_one(sample_image, tmp_dir):
    r = run_points([str(sample_image)])
    assert r.returncode != 0


def test_points_model_must_match_prep(sample_image, tmp_dir):
    """If prep was run with --model opus-4.7, points must use same --model."""
    r = run_points([
        str(sample_image), "--region", "50,25,150,75",
        "--model", "opus-4.7",
        "--points", "0,0", "--round",
    ])
    assert r.returncode == 0
    data = json.loads(r.stdout)
    assert data["points"] == [[50, 25]]
