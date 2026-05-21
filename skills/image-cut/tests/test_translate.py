"""Tests for tools/translate.py"""
import json
import subprocess
import sys


def run_translate(args):
    return subprocess.run(
        [sys.executable, "tools/translate.py", *args],
        capture_output=True, text=True,
    )


def make_crop_receipt(path, in_path, in_size, out_path, out_size, bbox):
    data = {
        "input": {"path": str(in_path), "size": list(in_size)},
        "output": {"path": str(out_path), "size": list(out_size)},
        "op": {"op": "crop", "bbox": list(bbox)},
    }
    path.write_text(json.dumps(data))
    return path


def make_resize_receipt(path, in_path, in_size, out_path, out_size, mode):
    data = {
        "input": {"path": str(in_path), "size": list(in_size)},
        "output": {"path": str(out_path), "size": list(out_size)},
        "op": {
            "op": "resize", "mode": mode,
            "in_size": list(in_size), "out_size": list(out_size),
        },
    }
    path.write_text(json.dumps(data))
    return path


def make_pad_receipt(path, in_path, in_size, out_path, out_size, pads):
    data = {
        "input": {"path": str(in_path), "size": list(in_size)},
        "output": {"path": str(out_path), "size": list(out_size)},
        "op": {"op": "pad", "pad": pads, "color": "#000000"},
    }
    path.write_text(json.dumps(data))
    return path


def test_translate_single_crop_to_global(tmp_dir):
    r1 = make_crop_receipt(
        tmp_dir / "r1.json",
        "orig.png", (1000, 800), "out.png", (200, 100),
        bbox=(100, 50, 300, 150),
    )
    result = run_translate([
        "--chain", str(r1), "--point", "10,20", "--to", "global", "--round",
    ])
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["global"] == [110, 70]


def test_translate_single_crop_to_local(tmp_dir):
    r1 = make_crop_receipt(
        tmp_dir / "r1.json",
        "orig.png", (1000, 800), "out.png", (200, 100),
        bbox=(100, 50, 300, 150),
    )
    result = run_translate([
        "--chain", str(r1), "--point", "110,70", "--to", "local", "--round",
    ])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["local"] == [10, 20]


def test_translate_bbox(tmp_dir):
    r1 = make_crop_receipt(
        tmp_dir / "r1.json",
        "orig.png", (1000, 800), "out.png", (200, 100),
        bbox=(100, 50, 300, 150),
    )
    result = run_translate([
        "--chain", str(r1), "--bbox", "10,10,50,40", "--to", "global", "--round",
    ])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["global"] == [110, 60, 150, 90]


def test_translate_chain_crop_then_resize(tmp_dir):
    """Crop 1000x800 → 400x200 region (100, 50, 500, 250).
    Then resize 400x200 → 200x100 (half-size).
    Point (50, 25) in final image should map back to:
      - undo resize: (100, 50) in cropped
      - undo crop: (100+100, 50+50) = (200, 100) in original
    """
    r1 = make_crop_receipt(
        tmp_dir / "r1.json",
        "orig.png", (1000, 800), "crop.png", (400, 200),
        bbox=(100, 50, 500, 250),
    )
    r2 = make_resize_receipt(
        tmp_dir / "r2.json",
        "crop.png", (400, 200), "resized.png", (200, 100),
        mode="scale",
    )
    result = run_translate([
        "--chain", str(r1), str(r2),
        "--point", "50,25", "--to", "global", "--round",
    ])
    assert result.returncode == 0, result.stderr
    data = json.loads(result.stdout)
    assert data["global"] == [200, 100]


def test_translate_chain_with_pad(tmp_dir):
    """Pad adds margins, shifting local coords. Origin (0,0) of padded image
    maps to (-pad_left, -pad_top) in the unpadded image.
    """
    r1 = make_pad_receipt(
        tmp_dir / "r1.json",
        "in.png", (100, 100), "out.png", (130, 120),
        pads={"top": 10, "right": 20, "bottom": 10, "left": 30},
    )
    result = run_translate([
        "--chain", str(r1), "--point", "0,0", "--to", "global", "--round",
    ])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["global"] == [-30, -10]


def test_translate_chain_mismatch_errors(tmp_dir):
    r1 = make_crop_receipt(
        tmp_dir / "r1.json",
        "a.png", (1000, 800), "b.png", (200, 100),
        bbox=(0, 0, 200, 100),
    )
    r2 = make_resize_receipt(
        tmp_dir / "r2.json",
        "WRONG.png", (200, 100), "c.png", (100, 50),
        mode="scale",
    )
    result = run_translate([
        "--chain", str(r1), str(r2),
        "--point", "0,0", "--to", "global",
    ])
    assert result.returncode != 0
    assert "mismatch" in result.stderr.lower() or "chain" in result.stderr.lower()


def test_translate_emits_floats_without_round(tmp_dir):
    r1 = make_resize_receipt(
        tmp_dir / "r1.json",
        "in.png", (100, 100), "out.png", (33, 33),
        mode="fit-width",
    )
    result = run_translate([
        "--chain", str(r1), "--point", "10,10", "--to", "global",
    ])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert isinstance(data["global"][0], float)


def test_translate_point_or_bbox_required(tmp_dir):
    r1 = make_crop_receipt(
        tmp_dir / "r1.json",
        "a.png", (100, 100), "b.png", (50, 50),
        bbox=(0, 0, 50, 50),
    )
    result = run_translate(["--chain", str(r1), "--to", "global"])
    assert result.returncode != 0


def test_translate_resize_local_direction(tmp_dir):
    """100x100 → 50x50 (half-scale). Global (40, 60) → local (20, 30)."""
    r1 = make_resize_receipt(
        tmp_dir / "r1.json",
        "in.png", (100, 100), "out.png", (50, 50),
        mode="scale",
    )
    result = run_translate([
        "--chain", str(r1), "--point", "40,60", "--to", "local", "--round",
    ])
    assert result.returncode == 0
    data = json.loads(result.stdout)
    assert data["local"] == [20, 30]
