# Image-Cut Tools Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Build six Python CLI tools that let an agent isolate UI elements from website screenshots as clean image slices with deterministic coordinate translation across crop/pad/resize transforms.

**Architecture:** Each tool is a standalone script in `tools/`. Geometric ops (crop, pad, resize) write a sidecar JSON receipt at `<output>.json` and echo the same to stdout. `translate.py` composes receipt chains to map points/bboxes between transformed and original images. Shared helpers (receipt writing, image I/O, color parsing) live in `tools/_common.py`. Tests use pytest with a small fixture image.

**Tech Stack:** Python 3, Pillow 12, pytest 8.

---

## File Structure

**Create:**
- `tools/_common.py` — shared helpers: receipt writing, image save with quality, hex color parser, integer parser
- `tools/info.py` — print image metadata + vision_safe check
- `tools/crop.py` — crop by bbox
- `tools/pad.py` — add per-side margins with fill color
- `tools/resize.py` — fit-width / fit-height / explicit / scale
- `tools/convert.py` — format conversion (terminal op, no receipt)
- `tools/translate.py` — compose receipt chain, translate point/bbox
- `tests/conftest.py` — pytest fixtures (sample image generator)
- `tests/test_common.py`
- `tests/test_info.py`
- `tests/test_crop.py`
- `tests/test_pad.py`
- `tests/test_resize.py`
- `tests/test_convert.py`
- `tests/test_translate.py`
- `SKILL.md` — agent-facing workflow + tool reference
- `README.md` — human reference
- `pyproject.toml` — declare Pillow + pytest deps for reproducibility

**Receipt schema (all geometric ops):**
```json
{
  "input":  {"path": "page.png",  "size": [1920, 1080]},
  "output": {"path": "slice.png", "size": [800, 600]},
  "op": {"op": "crop", "bbox": [120, 200, 920, 800]}
}
```

The `op` object varies by tool:
- `crop`: `{"op": "crop", "bbox": [x1, y1, x2, y2]}`
- `pad`: `{"op": "pad", "pad": {"top": N, "right": N, "bottom": N, "left": N}, "color": "#000000"}`
- `resize`: `{"op": "resize", "mode": "fit-width|fit-height|explicit|scale", "in_size": [w, h], "out_size": [w, h]}`

`info.py` and `convert.py` do NOT write receipts.

---

### Task 1: Project scaffolding

**Files:**
- Create: `pyproject.toml`
- Create: `.gitignore`
- Create: `tests/__init__.py` (empty)
- Create: `tools/__init__.py` (empty)

- [ ] **Step 1: Write `pyproject.toml`**

```toml
[project]
name = "image-cut"
version = "0.1.0"
description = "Image cutting tools for agent-driven pixel-perfect HTML rebuilds"
requires-python = ">=3.10"
dependencies = ["Pillow>=10.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Write `.gitignore`**

```
__pycache__/
*.pyc
.pytest_cache/
.venv/
*.png.json
*.webp.json
*.jpg.json
tests/_tmp/
```

- [ ] **Step 3: Create empty `__init__.py` files**

Run:
```bash
touch tools/__init__.py tests/__init__.py
```

- [ ] **Step 4: Verify pytest discovers no tests yet**

Run: `pytest -v`
Expected: `no tests ran`, exit code 5 (no tests collected) — this confirms setup is wired correctly.

- [ ] **Step 5: Commit**

```bash
git init
git add pyproject.toml .gitignore tools/__init__.py tests/__init__.py
git commit -m "chore: scaffold image-cut project"
```

---

### Task 2: Test fixtures (conftest.py)

**Files:**
- Create: `tests/conftest.py`

- [ ] **Step 1: Write `conftest.py`**

```python
"""Pytest fixtures for image-cut tests."""
from pathlib import Path
import pytest
from PIL import Image


@pytest.fixture
def tmp_dir(tmp_path):
    """Return a Path for temporary test artifacts."""
    return tmp_path


@pytest.fixture
def sample_image(tmp_dir):
    """Create a 200x100 RGB image with a known pattern.

    Pattern: red top-half, blue bottom-half, with a single green pixel at (50, 25).
    """
    img = Image.new("RGB", (200, 100), "red")
    for y in range(50, 100):
        for x in range(200):
            img.putpixel((x, y), (0, 0, 255))
    img.putpixel((50, 25), (0, 255, 0))
    path = tmp_dir / "sample.png"
    img.save(path)
    return path


@pytest.fixture
def large_image(tmp_dir):
    """Create a 2000x1500 image — non-vision-safe (long edge > 1568)."""
    img = Image.new("RGB", (2000, 1500), "white")
    path = tmp_dir / "large.png"
    img.save(path)
    return path


@pytest.fixture
def portrait_image(tmp_dir):
    """Create a 600x900 image — portrait orientation."""
    img = Image.new("RGB", (600, 900), "white")
    path = tmp_dir / "portrait.png"
    img.save(path)
    return path
```

- [ ] **Step 2: Verify fixtures load**

Run: `pytest tests/conftest.py -v`
Expected: `no tests ran` (it's a fixtures file, not a test file) — no syntax errors.

- [ ] **Step 3: Commit**

```bash
git add tests/conftest.py
git commit -m "test: add pytest fixtures for sample images"
```

---

### Task 3: `_common.py` — shared helpers

**Files:**
- Create: `tools/_common.py`
- Create: `tests/test_common.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for tools/_common.py shared helpers."""
import json
from pathlib import Path
import pytest
from tools._common import (
    write_receipt,
    parse_hex_color,
    save_image_with_quality,
)
from PIL import Image


def test_write_receipt_creates_sidecar_and_returns_json(tmp_path):
    out_path = tmp_path / "out.png"
    receipt = write_receipt(
        out_path=out_path,
        input_path=Path("in.png"),
        input_size=(100, 50),
        output_size=(80, 40),
        op={"op": "crop", "bbox": [10, 5, 90, 45]},
    )
    sidecar = tmp_path / "out.png.json"
    assert sidecar.exists()
    data = json.loads(sidecar.read_text())
    assert data["input"]["path"] == "in.png"
    assert data["input"]["size"] == [100, 50]
    assert data["output"]["path"] == "out.png"
    assert data["output"]["size"] == [80, 40]
    assert data["op"]["op"] == "crop"
    assert receipt == data


def test_parse_hex_color_three_digit():
    assert parse_hex_color("#000") == (0, 0, 0)
    assert parse_hex_color("#fff") == (255, 255, 255)
    assert parse_hex_color("#f0a") == (255, 0, 170)


def test_parse_hex_color_six_digit():
    assert parse_hex_color("#000000") == (0, 0, 0)
    assert parse_hex_color("#ffffff") == (255, 255, 255)
    assert parse_hex_color("#ff8040") == (255, 128, 64)


def test_parse_hex_color_without_hash():
    assert parse_hex_color("000000") == (0, 0, 0)


def test_parse_hex_color_invalid_raises():
    with pytest.raises(ValueError):
        parse_hex_color("not-a-color")
    with pytest.raises(ValueError):
        parse_hex_color("#12345")


def test_save_image_with_quality_jpg(tmp_path):
    img = Image.new("RGB", (10, 10), "red")
    out = tmp_path / "out.jpg"
    save_image_with_quality(img, out, quality=80)
    assert out.exists()
    reopened = Image.open(out)
    assert reopened.size == (10, 10)
    assert reopened.format == "JPEG"


def test_save_image_with_quality_webp(tmp_path):
    img = Image.new("RGB", (10, 10), "red")
    out = tmp_path / "out.webp"
    save_image_with_quality(img, out, quality=98)
    assert out.exists()


def test_save_image_with_quality_png_ignores_quality(tmp_path):
    img = Image.new("RGB", (10, 10), "red")
    out = tmp_path / "out.png"
    save_image_with_quality(img, out, quality=50)
    assert out.exists()
    reopened = Image.open(out)
    assert reopened.format == "PNG"
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_common.py -v`
Expected: ImportError — `tools._common` does not exist yet.

- [ ] **Step 3: Implement `tools/_common.py`**

```python
"""Shared helpers for image-cut tools."""
from __future__ import annotations
import json
import sys
from pathlib import Path
from typing import Any
from PIL import Image


def write_receipt(
    out_path: Path,
    input_path: Path,
    input_size: tuple[int, int],
    output_size: tuple[int, int],
    op: dict[str, Any],
) -> dict[str, Any]:
    """Write a sidecar receipt at <out_path>.json and echo to stdout.

    Returns the receipt dict.
    """
    receipt = {
        "input": {"path": str(input_path), "size": list(input_size)},
        "output": {"path": str(out_path), "size": list(output_size)},
        "op": op,
    }
    sidecar = Path(str(out_path) + ".json")
    sidecar.write_text(json.dumps(receipt))
    print(json.dumps(receipt), file=sys.stdout)
    return receipt


def parse_hex_color(s: str) -> tuple[int, int, int]:
    """Parse a 3- or 6-digit hex color string into an (r, g, b) tuple."""
    s = s.lstrip("#")
    if len(s) == 3:
        try:
            return tuple(int(c * 2, 16) for c in s)  # type: ignore[return-value]
        except ValueError as e:
            raise ValueError(f"invalid hex color: #{s}") from e
    if len(s) == 6:
        try:
            return (int(s[0:2], 16), int(s[2:4], 16), int(s[4:6], 16))
        except ValueError as e:
            raise ValueError(f"invalid hex color: #{s}") from e
    raise ValueError(f"invalid hex color: #{s} (must be 3 or 6 hex digits)")


def save_image_with_quality(img: Image.Image, out_path: Path, quality: int) -> None:
    """Save image, applying quality only to jpg/webp."""
    ext = out_path.suffix.lower().lstrip(".")
    save_kwargs: dict[str, Any] = {}
    if ext in {"jpg", "jpeg"}:
        save_kwargs["quality"] = quality
        if img.mode in {"RGBA", "LA", "P"}:
            img = img.convert("RGB")
    elif ext == "webp":
        save_kwargs["quality"] = quality
    img.save(out_path, **save_kwargs)
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_common.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/_common.py tests/test_common.py
git commit -m "feat: add _common helpers (receipt, color, save)"
```

---

### Task 4: `info.py`

**Files:**
- Create: `tools/info.py`
- Create: `tests/test_info.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_info.py -v`
Expected: All tests fail — `tools/info.py` does not exist.

- [ ] **Step 3: Implement `tools/info.py`**

```python
#!/usr/bin/env python3
"""Print metadata about an image, including a vision_safe check.

Usage: info.py INPUT
"""
from __future__ import annotations
import argparse
import json
import sys
from math import gcd
from pathlib import Path
from PIL import Image


def aspect_ratio(w: int, h: int) -> str:
    g = gcd(w, h)
    return f"{w // g}:{h // g}"


def is_vision_safe(w: int, h: int) -> bool:
    """True when long edge <=1568 AND width >= height (landscape or square)."""
    return max(w, h) <= 1568 and w >= h


def main() -> int:
    parser = argparse.ArgumentParser(description="Print image metadata as JSON.")
    parser.add_argument("input", type=Path)
    args = parser.parse_args()
    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2
    with Image.open(args.input) as img:
        w, h = img.size
        info = {
            "path": str(args.input),
            "width": w,
            "height": h,
            "aspect": aspect_ratio(w, h),
            "format": img.format,
            "mode": img.mode,
            "size_bytes": args.input.stat().st_size,
            "vision_safe": is_vision_safe(w, h),
        }
    print(json.dumps(info))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_info.py -v`
Expected: 5 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/info.py tests/test_info.py
git commit -m "feat: add info.py — metadata + vision-safe check"
```

---

### Task 5: `crop.py`

**Files:**
- Create: `tools/crop.py`
- Create: `tests/test_crop.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_crop.py -v`
Expected: All tests fail — `tools/crop.py` does not exist.

- [ ] **Step 3: Implement `tools/crop.py`**

```python
#!/usr/bin/env python3
"""Crop an image to a bbox.

Usage: crop.py INPUT --bbox x1,y1,x2,y2 [--quality N=98] --out PATH
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from PIL import Image
from tools._common import write_receipt, save_image_with_quality


def parse_bbox(s: str) -> tuple[int, int, int, int]:
    parts = s.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"bbox must be x1,y1,x2,y2 — got: {s!r}"
        )
    try:
        x1, y1, x2, y2 = (int(p) for p in parts)
    except ValueError as e:
        raise argparse.ArgumentTypeError(
            f"bbox values must be integers — got: {s!r}"
        ) from e
    return x1, y1, x2, y2


def main() -> int:
    parser = argparse.ArgumentParser(description="Crop an image to a bbox.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--bbox", type=parse_bbox, required=True)
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    x1, y1, x2, y2 = args.bbox
    if x1 >= x2 or y1 >= y2:
        print(
            f"error: bbox must have x1<x2 and y1<y2 — got {args.bbox}",
            file=sys.stderr,
        )
        return 2
    if x1 < 0 or y1 < 0:
        print(
            f"error: bbox has negative coordinates — got {args.bbox}",
            file=sys.stderr,
        )
        return 2

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    with Image.open(args.input) as img:
        in_w, in_h = img.size
        if x2 > in_w or y2 > in_h:
            print(
                f"error: bbox {args.bbox} exceeds image bounds "
                f"({in_w}x{in_h})",
                file=sys.stderr,
            )
            return 2
        cropped = img.crop((x1, y1, x2, y2))
        save_image_with_quality(cropped, args.out, args.quality)
        out_w, out_h = cropped.size

    write_receipt(
        out_path=args.out,
        input_path=args.input,
        input_size=(in_w, in_h),
        output_size=(out_w, out_h),
        op={"op": "crop", "bbox": [x1, y1, x2, y2]},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_crop.py -v`
Expected: 8 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/crop.py tests/test_crop.py
git commit -m "feat: add crop.py — crop by bbox with receipt"
```

---

### Task 6: `pad.py`

**Files:**
- Create: `tools/pad.py`
- Create: `tests/test_pad.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_pad.py -v`
Expected: All tests fail — `tools/pad.py` does not exist.

- [ ] **Step 3: Implement `tools/pad.py`**

```python
#!/usr/bin/env python3
"""Add per-side margins to an image.

Usage: pad.py INPUT [--pad-top N] [--pad-right N] [--pad-bottom N]
                    [--pad-left N] [--color #000000] [--quality N=98]
                    --out PATH
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from PIL import Image
from tools._common import write_receipt, parse_hex_color, save_image_with_quality


def main() -> int:
    parser = argparse.ArgumentParser(description="Add per-side margins to an image.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--pad-top", type=int, default=0)
    parser.add_argument("--pad-right", type=int, default=0)
    parser.add_argument("--pad-bottom", type=int, default=0)
    parser.add_argument("--pad-left", type=int, default=0)
    parser.add_argument("--color", default="#000000")
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    pads = {
        "top": args.pad_top,
        "right": args.pad_right,
        "bottom": args.pad_bottom,
        "left": args.pad_left,
    }
    if all(v == 0 for v in pads.values()):
        print(
            "error: at least one of --pad-top/--pad-right/--pad-bottom/"
            "--pad-left must be > 0",
            file=sys.stderr,
        )
        return 2
    if any(v < 0 for v in pads.values()):
        print("error: pad values must be non-negative", file=sys.stderr)
        return 2

    try:
        color_rgb = parse_hex_color(args.color)
    except ValueError as e:
        print(f"error: {e}", file=sys.stderr)
        return 2

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    with Image.open(args.input) as img:
        in_w, in_h = img.size
        new_w = in_w + pads["left"] + pads["right"]
        new_h = in_h + pads["top"] + pads["bottom"]
        if img.mode == "RGBA":
            fill = (*color_rgb, 255)
        else:
            fill = color_rgb
            if img.mode != "RGB":
                img = img.convert("RGB")
        padded = Image.new(img.mode, (new_w, new_h), fill)
        padded.paste(img, (pads["left"], pads["top"]))
        save_image_with_quality(padded, args.out, args.quality)

    # Normalize color to 6-digit lowercase for receipt
    color_hex = "#{:02x}{:02x}{:02x}".format(*color_rgb)
    write_receipt(
        out_path=args.out,
        input_path=args.input,
        input_size=(in_w, in_h),
        output_size=(new_w, new_h),
        op={"op": "pad", "pad": pads, "color": color_hex},
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_pad.py -v`
Expected: 7 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/pad.py tests/test_pad.py
git commit -m "feat: add pad.py — per-side margins with fill color"
```

---

### Task 7: `resize.py`

**Files:**
- Create: `tools/resize.py`
- Create: `tests/test_resize.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_resize.py -v`
Expected: All tests fail — `tools/resize.py` does not exist.

- [ ] **Step 3: Implement `tools/resize.py`**

```python
#!/usr/bin/env python3
"""Resize an image.

Modes (mutually exclusive):
  --fit-width N         scale so width = N, height proportional
  --fit-height N        scale so height = N, width proportional
  --width N --height N  both required, explicit size, may distort
  --scale F             multiply both dims by F
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from PIL import Image
from tools._common import write_receipt, save_image_with_quality


def main() -> int:
    parser = argparse.ArgumentParser(description="Resize an image.")
    parser.add_argument("input", type=Path)
    parser.add_argument("--fit-width", type=int)
    parser.add_argument("--fit-height", type=int)
    parser.add_argument("--width", type=int)
    parser.add_argument("--height", type=int)
    parser.add_argument("--scale", type=float)
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    # Mode resolution
    explicit_mode = args.width is not None or args.height is not None
    if explicit_mode and (args.width is None or args.height is None):
        print(
            "error: --width and --height must be used together",
            file=sys.stderr,
        )
        return 2
    modes_set = sum([
        args.fit_width is not None,
        args.fit_height is not None,
        explicit_mode,
        args.scale is not None,
    ])
    if modes_set == 0:
        print(
            "error: must specify one of --fit-width / --fit-height / "
            "(--width and --height) / --scale",
            file=sys.stderr,
        )
        return 2
    if modes_set > 1:
        print("error: resize modes are mutually exclusive", file=sys.stderr)
        return 2

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    with Image.open(args.input) as img:
        in_w, in_h = img.size
        if args.fit_width is not None:
            mode = "fit-width"
            out_w = args.fit_width
            out_h = max(1, round(in_h * out_w / in_w))
        elif args.fit_height is not None:
            mode = "fit-height"
            out_h = args.fit_height
            out_w = max(1, round(in_w * out_h / in_h))
        elif explicit_mode:
            mode = "explicit"
            out_w, out_h = args.width, args.height
        else:
            mode = "scale"
            out_w = max(1, round(in_w * args.scale))
            out_h = max(1, round(in_h * args.scale))

        if out_w <= 0 or out_h <= 0:
            print(
                f"error: resize produced non-positive size ({out_w}x{out_h})",
                file=sys.stderr,
            )
            return 2

        resized = img.resize((out_w, out_h), Image.Resampling.LANCZOS)
        save_image_with_quality(resized, args.out, args.quality)

    write_receipt(
        out_path=args.out,
        input_path=args.input,
        input_size=(in_w, in_h),
        output_size=(out_w, out_h),
        op={
            "op": "resize",
            "mode": mode,
            "in_size": [in_w, in_h],
            "out_size": [out_w, out_h],
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_resize.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/resize.py tests/test_resize.py
git commit -m "feat: add resize.py — fit/explicit/scale modes"
```

---

### Task 8: `convert.py`

**Files:**
- Create: `tools/convert.py`
- Create: `tests/test_convert.py`

- [ ] **Step 1: Write the failing tests**

```python
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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_convert.py -v`
Expected: All tests fail — `tools/convert.py` does not exist.

- [ ] **Step 3: Implement `tools/convert.py`**

```python
#!/usr/bin/env python3
"""Convert an image to a different format.

Terminal op — does not write a receipt. Default format is webp at quality 98.

Usage: convert.py INPUT [--format webp|png|jpg] [--quality N=98] --out PATH
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
from PIL import Image


FORMAT_TO_PIL = {"webp": "WEBP", "png": "PNG", "jpg": "JPEG", "jpeg": "JPEG"}


def main() -> int:
    parser = argparse.ArgumentParser(description="Convert image format.")
    parser.add_argument("input", type=Path)
    parser.add_argument(
        "--format",
        choices=["webp", "png", "jpg", "jpeg"],
        default="webp",
    )
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    pil_fmt = FORMAT_TO_PIL[args.format]
    save_kwargs: dict[str, int] = {}
    if pil_fmt in {"WEBP", "JPEG"}:
        save_kwargs["quality"] = args.quality

    with Image.open(args.input) as img:
        if pil_fmt == "JPEG" and img.mode in {"RGBA", "LA", "P"}:
            img = img.convert("RGB")
        img.save(args.out, format=pil_fmt, **save_kwargs)
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_convert.py -v`
Expected: 6 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/convert.py tests/test_convert.py
git commit -m "feat: add convert.py — terminal format conversion"
```

---

### Task 9: `translate.py`

**Files:**
- Create: `tools/translate.py`
- Create: `tests/test_translate.py`

- [ ] **Step 1: Write the failing tests**

```python
"""Tests for tools/translate.py"""
import json
import subprocess
import sys
from pathlib import Path


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
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `pytest tests/test_translate.py -v`
Expected: All tests fail — `tools/translate.py` does not exist.

- [ ] **Step 3: Implement `tools/translate.py`**

```python
#!/usr/bin/env python3
"""Translate a point or bbox across a chain of receipts.

Usage:
  translate.py --chain R1.json [R2.json ...]
               (--point x,y | --bbox x1,y1,x2,y2)
               --to global|local
               [--round]
"""
from __future__ import annotations
import argparse
import json
import sys
from pathlib import Path


def parse_point(s: str) -> tuple[float, float]:
    parts = s.split(",")
    if len(parts) != 2:
        raise argparse.ArgumentTypeError(f"point must be x,y — got: {s!r}")
    return float(parts[0]), float(parts[1])


def parse_bbox(s: str) -> tuple[float, float, float, float]:
    parts = s.split(",")
    if len(parts) != 4:
        raise argparse.ArgumentTypeError(
            f"bbox must be x1,y1,x2,y2 — got: {s!r}"
        )
    return tuple(float(p) for p in parts)  # type: ignore[return-value]


def map_local_to_input(op: dict, local: tuple[float, float]) -> tuple[float, float]:
    """Apply one op's local → input transform."""
    lx, ly = local
    kind = op["op"]
    if kind == "crop":
        x1, y1, _, _ = op["bbox"]
        return lx + x1, ly + y1
    if kind == "pad":
        pad = op["pad"]
        return lx - pad["left"], ly - pad["top"]
    if kind == "resize":
        in_w, in_h = op["in_size"]
        out_w, out_h = op["out_size"]
        return lx * in_w / out_w, ly * in_h / out_h
    raise ValueError(f"unknown op: {kind}")


def map_input_to_local(op: dict, inp: tuple[float, float]) -> tuple[float, float]:
    """Apply the inverse of one op (input → local)."""
    ix, iy = inp
    kind = op["op"]
    if kind == "crop":
        x1, y1, _, _ = op["bbox"]
        return ix - x1, iy - y1
    if kind == "pad":
        pad = op["pad"]
        return ix + pad["left"], iy + pad["top"]
    if kind == "resize":
        in_w, in_h = op["in_size"]
        out_w, out_h = op["out_size"]
        return ix * out_w / in_w, iy * out_h / in_h
    raise ValueError(f"unknown op: {kind}")


def load_receipts(paths: list[Path]) -> list[dict]:
    receipts = []
    for p in paths:
        if not p.exists():
            raise SystemExit(f"error: receipt not found: {p}")
        receipts.append(json.loads(p.read_text()))
    # Validate chain: each receipt's input.path must match previous output.path
    for i in range(1, len(receipts)):
        prev_out = receipts[i - 1]["output"]["path"]
        this_in = receipts[i]["input"]["path"]
        if prev_out != this_in:
            raise SystemExit(
                f"error: chain mismatch — receipt[{i-1}].output.path "
                f"{prev_out!r} != receipt[{i}].input.path {this_in!r}"
            )
    return receipts


def translate_point_to_global(
    receipts: list[dict], pt: tuple[float, float]
) -> tuple[float, float]:
    """Walk chain backwards (final → original) applying local→input."""
    cur = pt
    for r in reversed(receipts):
        cur = map_local_to_input(r["op"], cur)
    return cur


def translate_point_to_local(
    receipts: list[dict], pt: tuple[float, float]
) -> tuple[float, float]:
    """Walk chain forwards (original → final) applying input→local."""
    cur = pt
    for r in receipts:
        cur = map_input_to_local(r["op"], cur)
    return cur


def maybe_round(vals: list[float], do_round: bool) -> list:
    if do_round:
        return [int(round(v)) for v in vals]
    return list(vals)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Translate a point or bbox across a chain of receipts."
    )
    parser.add_argument("--chain", type=Path, nargs="+", required=True)
    group = parser.add_mutually_exclusive_group(required=True)
    group.add_argument("--point", type=parse_point)
    group.add_argument("--bbox", type=parse_bbox)
    parser.add_argument("--to", choices=["global", "local"], required=True)
    parser.add_argument("--round", action="store_true")
    args = parser.parse_args()

    try:
        receipts = load_receipts(args.chain)
    except SystemExit as e:
        print(e, file=sys.stderr)
        return 2

    translate = (
        translate_point_to_global if args.to == "global" else translate_point_to_local
    )

    if args.point is not None:
        out = translate(receipts, args.point)
        key = args.to
        print(json.dumps({key: maybe_round(list(out), args.round)}))
    else:
        x1, y1, x2, y2 = args.bbox
        p1 = translate(receipts, (x1, y1))
        p2 = translate(receipts, (x2, y2))
        bx1, by1 = min(p1[0], p2[0]), min(p1[1], p2[1])
        bx2, by2 = max(p1[0], p2[0]), max(p1[1], p2[1])
        key = args.to
        print(json.dumps({key: maybe_round([bx1, by1, bx2, by2], args.round)}))
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 4: Run tests to verify they pass**

Run: `pytest tests/test_translate.py -v`
Expected: 9 passed.

- [ ] **Step 5: Commit**

```bash
git add tools/translate.py tests/test_translate.py
git commit -m "feat: add translate.py — compose receipt chain, map points/bboxes"
```

---

### Task 10: Full suite green + integration check

**Files:**
- None new

- [ ] **Step 1: Run full test suite**

Run: `pytest -v`
Expected: All tests pass across all six modules + common. Total ~52 tests.

- [ ] **Step 2: Run an end-to-end integration manually**

```bash
# Use the sample fixture-style image via a quick Python one-liner:
python -c "from PIL import Image; Image.new('RGB',(1000,800),'white').save('test_orig.png')"

# Rough crop
python tools/crop.py test_orig.png --bbox 100,200,500,400 --out rough.png

# Inspect
python tools/info.py rough.png

# Resize the rough to half size
python tools/resize.py rough.png --scale 0.5 --out small.png

# Translate point (50, 25) in small.png back to original coords
python tools/translate.py --chain rough.png.json small.png.json \
    --point 50,25 --to global --round
```

Expected last command output:
```json
{"global": [200, 250]}
```

(Reasoning: undo resize 0.5 → (100, 50) in rough; undo crop → (100+100, 50+200) = (200, 250).)

- [ ] **Step 3: Clean up integration artifacts**

```bash
rm -f test_orig.png rough.png rough.png.json small.png small.png.json
```

- [ ] **Step 4: Commit (if anything changed; usually nothing here)**

No commit unless integration revealed fixes.

---

### Task 11: SKILL.md

**Files:**
- Create: `SKILL.md`

- [ ] **Step 1: Write `SKILL.md`**

```markdown
---
name: image-cut
description: Use when an agent needs to isolate UI elements (icons, components, hero images, sections) from a website screenshot as clean image slices for pixel-perfect HTML reconstruction. Provides crop, pad, resize, format conversion, and deterministic coordinate translation across transform chains.
---

# Image-Cut

Tools for slicing website screenshots into pixel-perfect element images.

## When to use

You've been given a website screenshot and need to extract individual UI
elements (a button, a card, an icon, a hero image) as their own image files
for use in rebuilding the page in HTML.

## Workflow

### Step 1 — Estimate a rough bbox around the target

Look at the screenshot, identify the element you want to isolate, and pick a
generous bounding box around it. Coordinates will be imprecise — that's fine.

```bash
python tools/crop.py screenshot.png --bbox x1,y1,x2,y2 --out rough.png
```

This writes `rough.png` and `rough.png.json` (the receipt).

### Step 2 — Decide the precision path

Run `info.py` on `rough.png`:

```bash
python tools/info.py rough.png
```

- **If `width ≤ 300` and `height ≤ 300` and `vision_safe: true`:** use the
  **eyeball path** (Step 3a).
- **Else if `vision_safe: true`:** use the **per-edge path** (Step 3b).
- **Else (`vision_safe: false`):** resize the rough crop first:

  ```bash
  python tools/resize.py rough.png --fit-width 1456 --out rough_v.png
  ```

  Then proceed with eyeball or per-edge using `rough_v.png` and chaining
  `rough.png.json` + `rough_v.png.json` for translation.

### Step 3a — Eyeball path (target ≤300×300)

Look at `rough.png` directly. Identify the precise bbox of the target in
the rough image's local coordinates. Then translate to global:

```bash
python tools/translate.py --chain rough.png.json \
    --bbox lx1,ly1,lx2,ly2 --to global --round
```

Use the resulting global bbox in Step 4.

### Step 3b — Per-edge path (target >300×300)

For each of the four edges of the rough bbox, crop a small probe (~100×100)
from the **original** screenshot, centered on the rough edge:

```bash
python tools/crop.py screenshot.png --bbox <probe_bbox> --out top_edge.png
# ... repeat for right, bottom, left
```

Look at each probe. Identify the precise edge pixel in the probe's local
coordinates. Translate each to global:

```bash
python tools/translate.py --chain top_edge.png.json \
    --point lx,ly --to global --round
```

Collect the four precise edge values and assemble the final bbox.

### Step 4 — Final cut from the original

Always cut the final asset from the **original** screenshot using the precise
bbox, not from any intermediate rough/probe:

```bash
python tools/crop.py screenshot.png --bbox X1,Y1,X2,Y2 --out element.webp
```

Output defaults to webp at quality 98. To override:

```bash
python tools/crop.py screenshot.png --bbox X1,Y1,X2,Y2 \
    --quality 90 --out element.webp
```

For PNG output (no quality flag needed):

```bash
python tools/crop.py screenshot.png --bbox X1,Y1,X2,Y2 --out element.png
```

## Tool reference

| Tool | Purpose | Receipt |
|---|---|---|
| `info.py` | Metadata + vision_safe check | No |
| `crop.py` | Crop by bbox | Yes |
| `pad.py` | Add per-side margins | Yes |
| `resize.py` | Fit / explicit / scale | Yes |
| `convert.py` | Format conversion (terminal op) | No |
| `translate.py` | Map point/bbox across receipt chain | N/A |

See `README.md` for full flag documentation.

## Receipt chains

Every geometric op writes a `<output>.json` receipt. To translate coordinates
across multiple ops, pass receipts to `translate.py` in the order applied
(oldest first):

```bash
python tools/translate.py --chain step1.png.json step2.png.json step3.png.json \
    --point x,y --to global --round
```

The chain must be unbroken: `step2.json.input.path` must equal
`step1.json.output.path`, etc. Otherwise `translate.py` exits with an error.

`convert.py` is a terminal op and writes no receipt — don't place it in the
middle of a chain.

## Tips

- `--round` rounds translate output to ints. Use it when feeding coords to
  `crop.py`, which requires integer bboxes.
- Bbox is always `x1,y1,x2,y2` with `x1 < x2` and `y1 < y2`. `crop.py`
  rejects inverted or out-of-bounds bboxes.
- `pad.py` adds black margins by default; use `--color #ff0000` for a
  different fill.
- For source-pixel context around a target, just expand the bbox in
  `crop.py` — don't use `pad.py` (which only adds solid color).
```

- [ ] **Step 2: Commit**

```bash
git add SKILL.md
git commit -m "docs: add SKILL.md — agent-facing workflow"
```

---

### Task 12: README.md

**Files:**
- Create: `README.md`

- [ ] **Step 1: Write `README.md`**

```markdown
# image-cut

Six small Python CLIs for isolating UI elements from website screenshots,
with deterministic coordinate translation across transform chains.

## Install

```bash
pip install Pillow
# (optional, for running tests)
pip install pytest
```

## Tools

### `info.py`

```
info.py INPUT
```

Prints JSON: `path`, `width`, `height`, `aspect`, `format`, `mode`,
`size_bytes`, `vision_safe`.

`vision_safe` is true when long edge ≤1568px and width ≥ height
(landscape/square). Used by agents to decide whether a region can be
inspected by Claude's vision model without internal downscaling.

### `crop.py`

```
crop.py INPUT --bbox x1,y1,x2,y2 [--quality N=98] --out PATH
```

Bbox in pixel coordinates of `INPUT`. Output format inferred from `--out`
extension. Writes a sidecar receipt at `<out>.json`.

### `pad.py`

```
pad.py INPUT [--pad-top N] [--pad-right N] [--pad-bottom N] [--pad-left N]
             [--color #000000] [--quality N=98] --out PATH
```

Adds margins outside the source pixels. Default fill color black.

### `resize.py`

```
resize.py INPUT (--fit-width N | --fit-height N |
                 (--width N --height N) | --scale F)
              [--quality N=98] --out PATH
```

Mutually exclusive resize modes. `--width` and `--height` must be used
together (explicit size, may distort). Others preserve aspect.

### `convert.py`

```
convert.py INPUT [--format webp|png|jpg] [--quality N=98] --out PATH
```

Format conversion only — no geometric change, no receipt. Default format
webp at quality 98.

### `translate.py`

```
translate.py --chain R1.json [R2.json ...]
             (--point x,y | --bbox x1,y1,x2,y2)
             --to global|local
             [--round]
```

Translate a point or bbox across a chain of receipts.

- `--to global` — convert coordinates in the final transformed image back to
  the original input's pixel space.
- `--to local` — convert original-input coordinates to the final image.
- `--round` — round outputs to nearest integer (default emits floats).

Chain validation: each receipt's `input.path` must equal the previous
receipt's `output.path`.

## Receipt format

Every geometric op writes `<output>.json`:

```json
{
  "input":  {"path": "page.png",  "size": [1920, 1080]},
  "output": {"path": "slice.png", "size": [800, 600]},
  "op": {"op": "crop", "bbox": [120, 200, 920, 800]}
}
```

The `op` object varies by tool:
- crop: `{"op": "crop", "bbox": [x1, y1, x2, y2]}`
- pad: `{"op": "pad", "pad": {"top": N, "right": N, "bottom": N, "left": N}, "color": "#rrggbb"}`
- resize: `{"op": "resize", "mode": "fit-width|fit-height|explicit|scale", "in_size": [w, h], "out_size": [w, h]}`

## Tests

```bash
pytest -v
```

## Agent workflow

See `SKILL.md` for the end-to-end workflow an agent follows to extract
UI elements from a screenshot.
```

- [ ] **Step 2: Commit**

```bash
git add README.md
git commit -m "docs: add README.md"
```

---

## Self-Review

**Spec coverage:**
- ✓ Six tools, all built (Tasks 4–9)
- ✓ Pillow stack (Task 1)
- ✓ Sidecar receipts for geometric ops; `info.py` and `convert.py` skip receipts (Task 3 + per-tool tasks)
- ✓ Tiered workflow (eyeball ≤300 / per-edge / resize-first) documented in SKILL.md (Task 11)
- ✓ webp + q=98 defaults (Tasks 8, 5, 6, 7)
- ✓ Translate math: crop/pad/resize op maps (Task 9)
- ✓ Chain mismatch error (Task 9 test `test_translate_chain_mismatch_errors`)
- ✓ Out-of-scope items not built: no ImageMagick, no OpenAI integration, no vision_prep, no center-crop, no pad-during-crop, no chained-CLI

**Placeholder scan:** No TBDs, no "implement later", no "similar to Task N" — every code block is complete.

**Type consistency:**
- `write_receipt` signature matches its callers in crop/pad/resize.
- Receipt `op` shapes match across writers (crop/pad/resize) and reader (`translate.py`).
- `parse_bbox` returns `tuple[int, int, int, int]` in `crop.py`, `tuple[float, ...]` in `translate.py` — different on purpose (crop wants ints; translate accepts fractional points).
