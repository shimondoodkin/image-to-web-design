"""Tests for tools/vision_prep.py — OpenAI vision pipeline mirror."""
import json
import subprocess
import sys
from PIL import Image


def expected_openai(in_w, in_h):
    """Mirror the algorithm under test (validation report §5.3)."""
    s1 = min(1.0, 2048 / max(in_w, in_h))
    short_after_s1 = min(in_w * s1, in_h * s1)
    s2 = 768 / short_after_s1 if short_after_s1 > 768 else 1.0
    scale = s1 * s2
    sw = max(1, round(in_w * scale))
    sh = max(1, round(in_h * scale))
    return scale, (sw, sh)


def run_vp(args):
    return subprocess.run(
        [sys.executable, "tools/vision_prep.py", *args],
        capture_output=True, text=True,
    )


def make_image(path, size, color="white"):
    Image.new("RGB", size, color).save(path)
    return path


def test_vp_small_square_passes_through(tmp_dir):
    """500x500 < 768 shortest-side and < 2048 long-edge → pass-through."""
    inp = make_image(tmp_dir / "in.png", (500, 500))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    assert Image.open(out).size == (500, 500)


def test_vp_exact_768_native(tmp_dir):
    """768x768 → 768x768 with scale=1.0 (the canonical OpenAI native size)."""
    inp = make_image(tmp_dir / "in.png", (768, 768))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    assert Image.open(out).size == (768, 768)
    data = json.loads((tmp_dir / "out.png.json").read_text())
    assert data["op"]["scale"] == 1.0


def test_vp_landscape_downscales_to_768_shortest(tmp_dir):
    """1600x900: stage1 no-op, stage2 scales so shortest=768."""
    inp = make_image(tmp_dir / "in.png", (1600, 900))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    _, expected = expected_openai(1600, 900)
    assert Image.open(out).size == expected
    w, h = expected
    assert min(w, h) == 768


def test_vp_oversized_uses_both_stages(tmp_dir):
    """3000x1500: stage1 downscales to fit 2048, stage2 then to 768 short."""
    inp = make_image(tmp_dir / "in.png", (3000, 1500))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    _, expected = expected_openai(3000, 1500)
    assert Image.open(out).size == expected
    w, h = expected
    assert min(w, h) == 768
    assert max(w, h) <= 2048


def test_vp_portrait_short_under_768(tmp_dir):
    """400x800: shortest=400 < 768 → no stage-2 rescale, native pass-through."""
    inp = make_image(tmp_dir / "in.png", (400, 800))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0, r.stderr
    assert Image.open(out).size == (400, 800)


def test_vp_receipt_shape(tmp_dir):
    """Receipt is compatible with translate.py: op.op == 'vision_prep' with scale."""
    inp = make_image(tmp_dir / "in.png", (1600, 900))
    out = tmp_dir / "out.png"
    r = run_vp([str(inp), "--out", str(out)])
    assert r.returncode == 0
    data = json.loads((tmp_dir / "out.png.json").read_text())
    assert data["op"]["op"] == "vision_prep"
    assert data["op"]["family"] == "openai"
    assert "scale" in data["op"]
    assert "scaled_size" in data["op"]
    expected_scale, expected_size = expected_openai(1600, 900)
    assert abs(data["op"]["scale"] - expected_scale) < 1e-9
    assert data["op"]["scaled_size"] == list(expected_size)
    assert data["output"]["size"] == list(expected_size)


def test_vp_translate_through_chain(tmp_dir):
    """Crop then vision_prep, translate (0,0) of vp output back to original."""
    screenshot = tmp_dir / "screen.png"
    Image.new("RGB", (3000, 3000), "white").save(screenshot)

    rough = tmp_dir / "rough.png"
    r = subprocess.run(
        [sys.executable, "tools/crop.py", str(screenshot),
         "--bbox", "100,200,2100,2200", "--out", str(rough)],
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
