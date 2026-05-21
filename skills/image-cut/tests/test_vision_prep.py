"""Tests for tools/vision_prep.py — Claude vision pipeline mirror."""
import json
import math
import subprocess
import sys
from PIL import Image


# Inline the same algorithm vision_prep uses, to compute expected sizes.
PAD_MULTIPLE = 28
MODEL_LIMITS = {
    "sonnet": (1568, 1568),     # (max_long_edge, max_tokens)
    "opus-4.6": (1568, 1568),
    "haiku": (1568, 1568),
    "opus-4.7": (2576, 4784),
}


def expected_sizes(in_w, in_h, model="sonnet"):
    """Mirror _compute_claude_target: floor + verify under cap.
    No padding — output = scaled dims."""
    max_long_edge, max_tokens = MODEL_LIMITS[model]
    max_pixels = max_tokens * 750
    long_edge_scale = max_long_edge / max(in_w, in_h)
    token_scale = math.sqrt(max_pixels / (in_w * in_h))
    scale = min(1.0, long_edge_scale, token_scale)
    sw = max(1, math.floor(in_w * scale))
    sh = max(1, math.floor(in_h * scale))
    while sw * sh > max_pixels and (sw > 1 or sh > 1):
        if sw >= sh:
            sw -= 1
        else:
            sh -= 1
    return scale, (sw, sh), (sw, sh)


def run_vp(args):
    return subprocess.run(
        [sys.executable, "tools/vision_prep.py", *args],
        capture_output=True, text=True,
    )


def make_image(path, size, color="white"):
    Image.new("RGB", size, color).save(path)
    return path


def test_vp_small_image_passes_through(tmp_dir):
    """500x500 (within sonnet limits) → emitted at native, no padding."""
    inp = make_image(tmp_dir / "in.png", (500, 500))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    assert img.size == (500, 500)


def test_vp_large_image_downscales(tmp_dir):
    """2000x1000 (exceeds sonnet limits) → downscale (no padding)."""
    inp = make_image(tmp_dir / "in.png", (2000, 1000))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    scale, _, expected_out = expected_sizes(2000, 1000)
    assert scale < 1.0
    img = Image.open(out)
    assert img.size == expected_out


def test_vp_output_under_token_cap(tmp_dir):
    """All outputs must satisfy w*h ≤ max_tokens * 750 (1,176,000 for sonnet)
    so Claude doesn't rescale. Multiple-of-28 is NOT required."""
    for size in [(800, 600), (1234, 567), (200, 100), (3000, 1500), (1100, 1100), (1084, 1084)]:
        inp = make_image(tmp_dir / f"in_{size[0]}x{size[1]}.png", size)
        out = tmp_dir / f"out_{size[0]}x{size[1]}.png"
        r = run_vp([str(inp), "--out", str(out)])
        assert r.returncode == 0
        img = Image.open(out)
        w, h = img.size
        assert max(w, h) <= 1568, f"{size}→{img.size}: exceeds long-edge cap"
        assert w * h <= 1568 * 750, f"{size}→{img.size}: {w*h} px exceeds token cap"


def test_vp_opus_47_allows_larger(tmp_dir):
    """A 2000x1000 image with opus-4.7 stays larger than with sonnet."""
    inp = make_image(tmp_dir / "in.png", (2000, 1000))
    out_sonnet = tmp_dir / "sonnet.png"
    out_opus = tmp_dir / "opus.png"
    r1 = run_vp([str(inp), "--model", "sonnet", "--out", str(out_sonnet)])
    r2 = run_vp([str(inp), "--model", "opus-4.7", "--out", str(out_opus)])
    assert r1.returncode == 0 and r2.returncode == 0
    s = Image.open(out_sonnet).size
    o = Image.open(out_opus).size
    assert o[0] * o[1] > s[0] * s[1]


def test_vp_no_padding(tmp_dir):
    """Native pass-through — no padding added on output."""
    inp = make_image(tmp_dir / "in.png", (500, 500), color="red")
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    # Every pixel of the output is source content (red)
    assert img.getpixel((0, 0)) == (255, 0, 0)
    assert img.getpixel((499, 499)) == (255, 0, 0)
    assert img.size == (500, 500)


def test_vp_receipt(tmp_dir):
    inp = make_image(tmp_dir / "in.png", (500, 500))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0
    data = json.loads((tmp_dir / "out.png.json").read_text())
    assert data["op"]["op"] == "vision_prep"
    assert data["op"]["model"] == "sonnet"
    assert data["op"]["scale"] == 1.0
    assert data["op"]["scaled_size"] == [500, 500]
    assert data["op"]["padded_size"] == [500, 500]
    assert data["op"]["color"] == "#000000"
    assert data["output"]["size"] == [500, 500]


def test_vp_portrait_input(tmp_dir):
    """Portrait input is fine — emitted at native size."""
    inp = make_image(tmp_dir / "in.png", (400, 800))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0
    img = Image.open(out)
    # 400x800: under cap → native pass-through
    assert img.size == (400, 800)


def test_vp_gemini_passes_small_through(tmp_dir):
    """Gemini accepts any size — small image emitted at native dims."""
    inp = make_image(tmp_dir / "in.png", (300, 200))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--model", "gemini-3-flash", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    assert img.size == (300, 200)


def test_vp_gemini_passes_medium_through(tmp_dir):
    """600x500 emitted at native — no padding, no rescaling."""
    inp = make_image(tmp_dir / "in.png", (600, 500))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--model", "gemini-3-flash", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    assert img.size == (600, 500)


def test_vp_gemini_passes_landscape_through(tmp_dir):
    """1000x500 emitted at native (within 2304² grid limit)."""
    inp = make_image(tmp_dir / "in.png", (1000, 500))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--model", "gemini-3-flash", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    assert img.size == (1000, 500)


def test_vp_gemini_passes_large_through(tmp_dir):
    """2000x2000 still within 3×3 grid (2304²) — emitted at native."""
    inp = make_image(tmp_dir / "in.png", (2000, 2000))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--model", "gemini-3-flash", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    assert img.size == (2000, 2000)


def test_vp_gemini_too_big_downscales(tmp_dir):
    """3000x3000 exceeds 3×3 grid → downscale to fit 2304x2304 (no pad)."""
    inp = make_image(tmp_dir / "in.png", (3000, 3000))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--model", "gemini-3-flash", "--out", str(out)])
    assert r.returncode == 0, r.stderr
    img = Image.open(out)
    assert img.size == (2304, 2304)
    data = json.loads((tmp_dir / "out.png.json").read_text())
    assert data["op"]["scale"] < 1.0


def test_vp_gemini_receipt(tmp_dir):
    inp = make_image(tmp_dir / "in.png", (600, 500))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--model", "gemini-2.5-pro", "--out", str(out)])
    assert r.returncode == 0
    data = json.loads((tmp_dir / "out.png.json").read_text())
    assert data["op"]["op"] == "vision_prep"
    assert data["op"]["family"] == "gemini"
    assert data["op"]["model"] == "gemini-2.5-pro"
    assert data["op"]["scale"] == 1.0
    assert data["op"]["scaled_size"] == [600, 500]
    assert data["op"]["padded_size"] == [600, 500]


def test_vp_translate_through_chain(tmp_dir):
    """Crop then vision_prep, translate (0,0) of vp output back to original."""
    screenshot = tmp_dir / "screen.png"
    Image.new("RGB", (1000, 1000), "white").save(screenshot)

    rough = tmp_dir / "rough.png"
    r = subprocess.run(
        [sys.executable, "tools/crop.py", str(screenshot),
         "--bbox", "100,200,600,700", "--out", str(rough)],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr

    vp = tmp_dir / "vp.png"
    r = run_vp([str(rough), "--out", str(vp)])
    assert r.returncode == 0, r.stderr

    # Point (0, 0) in vp output → source (0, 0) of rough → (100, 200) global.
    r = subprocess.run(
        [sys.executable, "tools/translate.py",
         "--chain", str(rough) + ".json", str(vp) + ".json",
         "--point", "0,0", "--to", "global", "--round"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr
    data = json.loads(r.stdout)
    assert data["global"] == [100, 200]
