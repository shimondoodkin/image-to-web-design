# image-to-web-design-chatgpt Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Add a self-contained `skills/image-to-web-design-chatgpt/` skill that walks ChatGPT through the full image → React pipeline using only ChatGPT-native primitives (768 px vision, built-in image gen, code interpreter + rembg).

**Architecture:** New top-level skill folder, structurally parallel to `skills/image-cut/`. Ships an OpenAI-only `tools/vision_prep.py` plus verbatim copies of `crop.py`, `translate.py`, and `_common.py` from `image-cut`. No code or text references to codex/gemini headless commands. The new skill is registered in `.claude-plugin/plugin.json` so plugin installs pick it up.

**Tech Stack:** Python 3.10+, Pillow, pytest. No new runtime dependencies beyond what `image-cut` already requires.

**Spec:** `docs/superpowers/specs/2026-05-25-image-to-web-design-chatgpt-design.md`

---

## File Structure

Created in this plan:

```
skills/image-to-web-design-chatgpt/
├── SKILL.md                       # Task 7
├── pyproject.toml                 # Task 1
├── tools/
│   ├── __init__.py                # Task 1 (empty)
│   ├── _common.py                 # Task 2 (verbatim copy from image-cut)
│   ├── crop.py                    # Task 2 (verbatim copy from image-cut)
│   ├── translate.py               # Task 3 (verbatim copy from image-cut)
│   └── vision_prep.py             # Task 5 (NEW, OpenAI-only)
└── tests/
    ├── conftest.py                # Task 4 (adapted from image-cut)
    └── test_vision_prep.py        # Task 4 (NEW)
```

Modified:

- `.claude-plugin/plugin.json` — Task 8 (register the new skill).

The skill folder is self-contained: every `import` resolves inside `tools/`. It does not import from `../image-cut/`. Duplication is intentional so ChatGPT can be pointed at this one folder without sibling coupling.

---

## Why crop.py and translate.py are verbatim copies

- **`crop.py`** has no model-specific code. It takes a bbox and saves a crop.
- **`translate.py`** walks receipts by their `op` field. The OpenAI `vision_prep.py` emits the same `op: "vision_prep"` receipt shape with a `scale` field — so the existing `translate.py` handles OpenAI receipts unchanged.
- **`_common.py`** is the small helper module both `crop.py` and `vision_prep.py` import.

If `image-cut` later changes any of these, **this skill does not change**. They are now independent forks by design.

---

## Why vision_prep.py is rewritten

`image-cut/tools/vision_prep.py` supports Claude and Gemini families via a `--model` flag. ChatGPT loads files into its sandbox; a multi-model CLI with `--model openai` muddies the skill. The new `vision_prep.py`:

- Has **no `--model` flag** (always OpenAI).
- Has **no `--color` flag** (the OpenAI pipeline does not pad, so no fill colour is needed).
- Implements the two-stage downscale-only algorithm from the validation report §5.3:
  1. Fit within 2048×2048 (downscale only).
  2. Scale so shortest side ≤ 768 px (downscale only — small inputs pass through unchanged).
- Emits a receipt with `op.op == "vision_prep"` and `op.scale` so `translate.py` works.

---

### Task 1: Scaffold folder + pyproject + empty package init

**Files:**
- Create: `skills/image-to-web-design-chatgpt/pyproject.toml`
- Create: `skills/image-to-web-design-chatgpt/tools/__init__.py`
- Create: `skills/image-to-web-design-chatgpt/tests/__init__.py`

- [ ] **Step 1: Create `pyproject.toml`**

```toml
[project]
name = "image-to-web-design-chatgpt"
version = "0.1.0"
description = "Self-contained ChatGPT-tuned skill for converting design images into React components."
requires-python = ">=3.10"
dependencies = ["Pillow>=10.0"]

[project.optional-dependencies]
dev = ["pytest>=8.0"]

[tool.pytest.ini_options]
testpaths = ["tests"]
pythonpath = ["."]
```

- [ ] **Step 2: Create empty `tools/__init__.py`**

```python
```

- [ ] **Step 3: Create empty `tests/__init__.py`**

```python
```

- [ ] **Step 4: Commit**

```bash
git add skills/image-to-web-design-chatgpt/
git commit -m "feat(chatgpt-skill): scaffold folder structure"
```

---

### Task 2: Copy `_common.py` and `crop.py` from image-cut

**Files:**
- Create: `skills/image-to-web-design-chatgpt/tools/_common.py`
- Create: `skills/image-to-web-design-chatgpt/tools/crop.py`

- [ ] **Step 1: Copy `_common.py` verbatim**

Source: `skills/image-cut/tools/_common.py`
Destination: `skills/image-to-web-design-chatgpt/tools/_common.py`

The full body to write is (no changes from the source):

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

- [ ] **Step 2: Copy `crop.py` verbatim**

Source: `skills/image-cut/tools/crop.py`
Destination: `skills/image-to-web-design-chatgpt/tools/crop.py`

```python
#!/usr/bin/env python3
"""Crop an image to a bbox.

Usage: crop.py INPUT --bbox x1,y1,x2,y2 [--quality N=98] --out PATH
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image
from _common import write_receipt, save_image_with_quality  # noqa: E402


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

- [ ] **Step 3: Smoke-test crop.py runs**

Run from repo root:

```bash
python -c "from PIL import Image; Image.new('RGB',(200,200),'red').save('/tmp/in.png')"
python skills/image-to-web-design-chatgpt/tools/crop.py /tmp/in.png --bbox 10,10,100,100 --out /tmp/out.png
```

Expected: stdout JSON receipt with `"op": "crop"` and exit code 0. File `/tmp/out.png` (90×90) and `/tmp/out.png.json` exist.

- [ ] **Step 4: Commit**

```bash
git add skills/image-to-web-design-chatgpt/tools/_common.py skills/image-to-web-design-chatgpt/tools/crop.py
git commit -m "feat(chatgpt-skill): copy _common.py and crop.py from image-cut"
```

---

### Task 3: Copy `translate.py` from image-cut

**Files:**
- Create: `skills/image-to-web-design-chatgpt/tools/translate.py`

- [ ] **Step 1: Copy `translate.py` verbatim**

Source: `skills/image-cut/tools/translate.py`
Destination: `skills/image-to-web-design-chatgpt/tools/translate.py`

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
    if kind == "vision_prep":
        # right/bottom pad only — no origin offset. Just undo the scale.
        scale = op["scale"]
        return lx / scale, ly / scale
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
    if kind == "vision_prep":
        scale = op["scale"]
        return ix * scale, iy * scale
    raise ValueError(f"unknown op: {kind}")


def load_receipts(paths: list[Path]) -> list[dict]:
    receipts = []
    for p in paths:
        if not p.exists():
            raise SystemExit(f"error: receipt not found: {p}")
        receipts.append(json.loads(p.read_text()))
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

- [ ] **Step 2: Smoke-test translate.py runs**

```bash
echo '{"input":{"path":"a","size":[100,100]},"output":{"path":"b","size":[50,50]},"op":{"op":"crop","bbox":[10,20,60,70]}}' > /tmp/r.json
python skills/image-to-web-design-chatgpt/tools/translate.py --chain /tmp/r.json --point 0,0 --to global --round
```

Expected stdout: `{"global": [10, 20]}` and exit code 0.

- [ ] **Step 3: Commit**

```bash
git add skills/image-to-web-design-chatgpt/tools/translate.py
git commit -m "feat(chatgpt-skill): copy translate.py from image-cut (model-agnostic)"
```

---

### Task 4: Add test scaffolding (`conftest.py`) and failing test for `vision_prep.py`

**Files:**
- Create: `skills/image-to-web-design-chatgpt/tests/conftest.py`
- Create: `skills/image-to-web-design-chatgpt/tests/test_vision_prep.py`

- [ ] **Step 1: Write `conftest.py`** (adapted from image-cut)

```python
"""Pytest fixtures for image-to-web-design-chatgpt tests."""
from pathlib import Path

import pytest
from PIL import Image


@pytest.fixture(autouse=True)
def _chdir_to_skill_root(monkeypatch):
    """Run each test with cwd = skills/image-to-web-design-chatgpt/ so the
    `tools/vision_prep.py`-style relative paths resolve regardless of
    where pytest was launched from.
    """
    skill_root = Path(__file__).resolve().parent.parent
    monkeypatch.chdir(skill_root)


@pytest.fixture
def tmp_dir(tmp_path):
    return tmp_path


def make_image(path, size, color="white"):
    Image.new("RGB", size, color).save(path)
    return path
```

- [ ] **Step 2: Write the failing test `test_vision_prep.py`**

The OpenAI pipeline (validation report §5.3):

1. Stage 1: `s1 = min(1.0, 2048 / max(w, h))` — downscale only.
2. Stage 2: `short_after_s1 = min(w, h) * s1`; `s2 = 768 / short_after_s1 if short_after_s1 > 768 else 1.0`.
3. `scale = s1 * s2`; output = `(round(w*scale), round(h*scale))`.

```python
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
```

- [ ] **Step 3: Run tests, confirm they fail**

```bash
cd skills/image-to-web-design-chatgpt
python -m pytest tests/test_vision_prep.py -v
```

Expected: every test FAILs (file `tools/vision_prep.py` does not exist).

- [ ] **Step 4: Commit (failing tests first)**

```bash
git add skills/image-to-web-design-chatgpt/tests/
git commit -m "test(chatgpt-skill): failing tests for OpenAI vision_prep"
```

---

### Task 5: Implement `vision_prep.py` (OpenAI-only)

**Files:**
- Create: `skills/image-to-web-design-chatgpt/tools/vision_prep.py`

- [ ] **Step 1: Write the implementation**

```python
#!/usr/bin/env python3
"""Pre-scale an image to match OpenAI's vision pipeline exactly.

OpenAI vision (detail:high) processes images in two stages:

  1. Scale to fit within 2048x2048 (downscale only, preserving aspect).
  2. Scale so the shortest side is 768 px (downscale only — small inputs
     pass through unchanged).

The processed image is what the model actually sees. By doing both
stages client-side we send exactly what the model processes — no
internal rescaling, and coordinates round-trip accurately
(validated to under 1.4 px noise in
docs/research/2026-05-12-vision-validation-report.md).

Usage:
  vision_prep.py INPUT [--quality N=98] --out PATH

No --model flag: this script is OpenAI-only. No --color flag: the
OpenAI pipeline does not pad, so no fill colour is needed.
"""
from __future__ import annotations
import argparse
import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
from PIL import Image, ImageFilter
from _common import write_receipt, save_image_with_quality  # noqa: E402


def compute_target(in_w: int, in_h: int) -> tuple[float, tuple[int, int]]:
    """Return (scale, (out_w, out_h)) for the OpenAI vision pipeline."""
    s1 = min(1.0, 2048 / max(in_w, in_h))
    short_after_s1 = min(in_w * s1, in_h * s1)
    s2 = 768 / short_after_s1 if short_after_s1 > 768 else 1.0
    scale = s1 * s2
    out_w = max(1, round(in_w * scale))
    out_h = max(1, round(in_h * scale))
    return scale, (out_w, out_h)


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Pre-scale an image to match OpenAI's vision pipeline."
    )
    parser.add_argument("input", type=Path)
    parser.add_argument("--quality", type=int, default=98)
    parser.add_argument("--out", type=Path, required=True)
    args = parser.parse_args()

    if not args.input.exists():
        print(f"error: input not found: {args.input}", file=sys.stderr)
        return 2

    with Image.open(args.input) as img:
        in_w, in_h = img.size
        if img.mode not in {"RGB", "RGBA"}:
            img = img.convert("RGB")

        scale, (out_w, out_h) = compute_target(in_w, in_h)

        if scale < 1.0:
            resized = img.resize((out_w, out_h), Image.Resampling.LANCZOS)
            resized = resized.filter(
                ImageFilter.UnsharpMask(radius=1, percent=80, threshold=0)
            )
        else:
            resized = img

        save_image_with_quality(resized, args.out, args.quality)

    write_receipt(
        out_path=args.out,
        input_path=args.input,
        input_size=(in_w, in_h),
        output_size=(out_w, out_h),
        op={
            "op": "vision_prep",
            "family": "openai",
            "scale": scale,
            "scaled_size": [out_w, out_h],
        },
    )
    return 0


if __name__ == "__main__":
    sys.exit(main())
```

- [ ] **Step 2: Run tests, confirm all pass**

```bash
cd skills/image-to-web-design-chatgpt
python -m pytest tests/test_vision_prep.py -v
```

Expected: all 6 tests PASS.

- [ ] **Step 3: Add an integration smoke test (`crop → vision_prep → translate` round-trip)**

Append to `tests/test_vision_prep.py`:

```python
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
```

- [ ] **Step 4: Run tests again, confirm all 7 pass**

```bash
cd skills/image-to-web-design-chatgpt
python -m pytest tests/test_vision_prep.py -v
```

Expected: 7 PASS.

- [ ] **Step 5: Commit**

```bash
git add skills/image-to-web-design-chatgpt/tools/vision_prep.py skills/image-to-web-design-chatgpt/tests/test_vision_prep.py
git commit -m "feat(chatgpt-skill): implement OpenAI vision_prep + chain integration test"
```

---

### Task 6: Add the `--help`-runs smoke check

A two-line sanity test that every tool's `--help` flag exits 0. Catches argparse regressions in copies without re-testing image-cut's logic.

**Files:**
- Create: `skills/image-to-web-design-chatgpt/tests/test_tools_help.py`

- [ ] **Step 1: Write the test**

```python
"""Smoke: every tool's --help exits 0. Catches argparse regressions on copies."""
import subprocess
import sys


def _help_ok(script: str) -> None:
    r = subprocess.run(
        [sys.executable, script, "--help"],
        capture_output=True, text=True,
    )
    assert r.returncode == 0, r.stderr


def test_crop_help():
    _help_ok("tools/crop.py")


def test_vision_prep_help():
    _help_ok("tools/vision_prep.py")


def test_translate_help():
    _help_ok("tools/translate.py")
```

- [ ] **Step 2: Run, confirm pass**

```bash
cd skills/image-to-web-design-chatgpt
python -m pytest tests/ -v
```

Expected: 10 PASS total (7 vision_prep + 3 help).

- [ ] **Step 3: Commit**

```bash
git add skills/image-to-web-design-chatgpt/tests/test_tools_help.py
git commit -m "test(chatgpt-skill): smoke-test --help on every tool"
```

---

### Task 7: Write `SKILL.md`

**Files:**
- Create: `skills/image-to-web-design-chatgpt/SKILL.md`

The skill is a single self-contained doc that walks ChatGPT from image to React. Use the spec's section list verbatim.

- [ ] **Step 1: Write SKILL.md**

````markdown
---
name: image-to-web-design-chatgpt
description: Use when ChatGPT receives a design image (screenshot, mockup, or painted reference) and needs to produce HTML/JSX/Tailwind that closely matches the source. Self-contained end-to-end pipeline tuned for ChatGPT: native image gen for asset isolation, rembg in the code interpreter for alpha matting, and the 768 px shortest-side vision rule for accurate audits.
---

# image-to-web-design (ChatGPT edition)

> **Part of the [image-to-web-design](https://github.com/shimondoodkin/image-to-web-design) kit.**
> Self-contained variant tuned for ChatGPT. The `tools/` directory next
> to this file contains everything the recipes call. If you found this
> SKILL.md on its own, the canonical kit is at the link above; install
> with `npx skills add shimondoodkin/image-to-web-design`.

## What this skill does

Take a design image (screenshot, mockup, or painted reference) and end with a JSX/Tailwind React component plus extracted assets that closely match the source. The pipeline is: audit → slice → isolate assets → synthesise JSX/Tailwind → visual diff → iterate.

## ChatGPT's toolset

You have three primitives. Everything else in this skill composes them.

**1. Vision at 768 px shortest-side.** OpenAI's vision pipeline (detail:high) scales any image to fit 2048×2048, then scales again so the shortest side is 768 px. The processed image is what you actually see. Send a square at 768×768 and you skip both rescales — coordinates round-trip with under 1.4 px noise. For non-square images, target shortest-side = 768. Use `tools/vision_prep.py` to do this mechanically.

**2. Native image generation for editing.** When you need to remove, isolate, or fill an area of an image (asset isolation, background extraction), use your built-in image edit capability directly. Give it a locational instruction and let it produce the edited image. Do not write a Python script that synthesises the edit — the native tool does it in one call.

**3. Code interpreter for deterministic work.** Cropping, padding, resizing, coordinate translation, alpha matting with `rembg`, side-by-side diffing — all runs in your Python sandbox. PIL is available; `rembg` can be installed with `pip install "rembg[cpu,cli]"` on first use.

**Routing rule.** If the operation is **visual and creative** (paint over, fill, remove), use native image gen. If the operation is **deterministic and geometric** (crop these pixels, resize to N), use the code interpreter. The two-step element-isolation recipe in §5 uses both in sequence.

## §3 Audit the source image

Before anything else, look at the source under the 768 px rule and list:

- **Elements:** every visible UI block (nav, hero, card, badge, footer …) with a one-line description.
- **Positions:** approximate `(x, y, w, h)` in **source-image space** — translate from what you saw if the image you looked at was downscaled.
- **Colours:** sample dominant colours as `#rrggbb` hex.
- **Fonts:** family + size guess for each text block.
- **Notes:** unusual constraints (gradients, decorative shapes, overlapping elements).

The audit is the input to every subsequent step. Don't skip it because the image "looks simple."

## §4 Slice the image

Run in your code interpreter:

```bash
python tools/vision_prep.py source.png --out source_v.png
```

Output: an image at OpenAI's native processing dimensions (≤2048 long-edge, ≤768 shortest-side). The accompanying `source_v.png.json` is a receipt recording the scale factor for coordinate translation.

For sub-regions:

```bash
python tools/crop.py source.png --bbox X1,Y1,X2,Y2 --out region.png
python tools/vision_prep.py region.png --out region_v.png
```

When you read a coordinate `(rx, ry)` off `region_v.png`, translate it back to source space:

```bash
python tools/translate.py --chain region.png.json region_v.png.json --point RX,RY --to global --round
```

### Inline fallback

If `tools/vision_prep.py` isn't available, paste this into your code interpreter — it does the same OpenAI vision_prep without the unsharp-mask polish:

```python
from PIL import Image
def openai_vision_prep(in_path, out_path):
    img = Image.open(in_path).convert("RGB")
    w, h = img.size
    s1 = min(1.0, 2048 / max(w, h))
    short = min(w * s1, h * s1)
    s2 = 768 / short if short > 768 else 1.0
    scale = s1 * s2
    if scale < 1.0:
        img = img.resize((max(1, round(w*scale)), max(1, round(h*scale))), Image.Resampling.LANCZOS)
    img.save(out_path)
    return scale, img.size

openai_vision_prep("source.png", "source_v.png")
```

Coordinate translation, inline: a coord `(rx, ry)` on the vision-prep output came from `(rx / scale, ry / scale)` in the input image. If the input was itself a crop at `(cx, cy)`, add the crop offset.

## §5 Isolate assets with native image gen

Two recipes. Both use your native image gen, not external CLIs.

### Element track (two steps: image gen → rembg)

Goal: a clean transparent PNG of a single component.

**Step 1 — flatten with native image gen.** Give it this instruction (locational, no negative preservation constraint):

> Keep only the {component description} in the {position}. Replace everything else with solid white #FFFFFF.

Concrete example for a red "NEW" badge in the top right:

> Keep only the red "NEW" badge in the top-right corner around (1700, 90). Replace everything else with solid white #FFFFFF.

**Step 2 — alpha matte with rembg.** In your code interpreter:

```bash
pip install "rembg[cpu,cli]"
rembg i flattened.png component.png
```

For complex foregrounds (band members, hands, hair against busy backgrounds):

```bash
rembg i -m bria-rmbg flattened.png component.png
```

For soft-edged subjects (painted hair, fur, watercolour):

```bash
rembg i -m birefnet-general flattened.png component.png
```

Record the component's original position and size from the audit so the synthesis step (§6) can place it correctly.

### Background track

Goal: a continuous patch of the background where a component used to be.

Instruction:

> Remove the {component description} in the {position}. Replace with a continuation of the surrounding painted texture only. Do not add new objects or text.

One call per element. After the editor returns the result, look at it. If the fill introduced invented content or visibly broken texture, retry with a tighter locational instruction or a tighter crop.

### Prompt conventions for native image gen

- **Be locational.** Mention where the target is — corner, coordinates, colour, position relative to another element.
- **Forbid invention.** End with *"Do not add new objects or text."* and, where relevant, *"Replace only with the surrounding texture."*
- **One element per call.** Multi-element instructions degrade fast.
- **Avoid negative preservation constraints.** Do not include *"Do not modify the subject itself"* or *"Do not change X"*. They confuse the editor and cause over-engineered execution paths.

## §6 Synthesise JSX/Tailwind

- **Component shape.** One React function component per visually distinct section (hero, nav, card grid). Tailwind utility classes for layout/spacing; raw CSS only when Tailwind cannot express it.
- **Asset embedding.** Isolated assets from §5 go in `public/` and are referenced by path. Coordinates from the §3 audit translate to Tailwind position utilities: `absolute top-[90px] right-[24px]`.
- **Typography.** Tailwind `font-` / `text-[Npx]` arbitrary values when no near match exists.
- **Colour.** Tailwind arbitrary values (`bg-[#a73c2f]`) — no theme extension for one-off projects.
- **Layout-drift fix.** If a region is misaligned after rendering, re-audit that specific region under the 768 px rule and adjust the offsets. Do not eyeball.

## §7 Visual diff

**Default path.** Ask the user to run the React component (`npm run dev` or equivalent), screenshot the rendered page, and upload that screenshot back. Compare both images under the 768 px rule. List concrete differences:

- Offset deltas (in source-image pixels) for each visibly misaligned element.
- Colour deltas as `#source → #rendered`.
- Missing or extra elements.

**"If you can" path.** If `playwright` is installable in your sandbox:

```bash
pip install playwright
playwright install chromium
```

Render the built page to PNG, side-by-side it with the source via PIL, and report the deltas without a round-trip through the user.

Iterate on the synthesis (§6) until the stop signals (§8) fire.

## §8 Stop signals

Accept the current draft when any of these is true:

- The largest pixel-level offset is under the threshold the user named at the start, or under **8 px** if no threshold was given.
- Two consecutive iterations changed the rendered output by less than one visual element each.
- The remaining differences are in areas the user already accepted earlier.

When you stop, hand back the React component code plus the list of extracted assets and their target paths under `public/`.
````

- [ ] **Step 2: Verify YAML frontmatter parses**

```bash
python -c "
import yaml, pathlib
p = pathlib.Path('skills/image-to-web-design-chatgpt/SKILL.md')
text = p.read_text(encoding='utf-8')
assert text.startswith('---'), 'no frontmatter'
fm = text.split('---', 2)[1]
data = yaml.safe_load(fm)
assert data['name'] == 'image-to-web-design-chatgpt'
assert 'description' in data
print('frontmatter OK:', data['name'])
"
```

Expected: prints `frontmatter OK: image-to-web-design-chatgpt`, exit 0. (Requires PyYAML; if missing, `pip install pyyaml` first.)

- [ ] **Step 3: Verify every `tools/*.py` referenced in SKILL.md exists**

```bash
python -c "
import re, pathlib
text = pathlib.Path('skills/image-to-web-design-chatgpt/SKILL.md').read_text(encoding='utf-8')
refs = set(re.findall(r'tools/[a-z_]+\.py', text))
root = pathlib.Path('skills/image-to-web-design-chatgpt')
for r in sorted(refs):
    assert (root / r).exists(), f'broken ref: {r}'
print('refs OK:', sorted(refs))
"
```

Expected: prints `refs OK: ['tools/crop.py', 'tools/translate.py', 'tools/vision_prep.py']`, exit 0.

- [ ] **Step 4: Commit**

```bash
git add skills/image-to-web-design-chatgpt/SKILL.md
git commit -m "feat(chatgpt-skill): write self-contained SKILL.md"
```

---

### Task 8: Register the skill in `.claude-plugin/plugin.json`

**Files:**
- Modify: `.claude-plugin/plugin.json`

- [ ] **Step 1: Add the new skill path**

Read current file:

```bash
cat .claude-plugin/plugin.json
```

Edit the `skills` array to add `./skills/image-to-web-design-chatgpt` as the last entry. After editing, the file should look exactly like:

```json
{
  "name": "image-to-web-design",
  "version": "0.1.0",
  "description": "A kit of agent-facing skills for converting design images into pixel-perfect React webpages: an atomic AI image-edit primitive, isolation recipes, cropping CLIs with reliable coordinate translation, and an end-to-end orchestrator that audits, synthesises, and visually diffs the result against the source.",
  "author": {
    "name": "Shimon Doodkin",
    "email": "shimondoodkin@gmail.com"
  },
  "keywords": [
    "image-editing",
    "react",
    "design-to-code",
    "vision",
    "skills",
    "image-cut",
    "agent-skill"
  ],
  "skills": [
    "./skills/image-edit-instruction",
    "./skills/image-isolation-technique",
    "./skills/image-cut",
    "./skills/image-to-web-design",
    "./skills/image-to-web-design-chatgpt"
  ]
}
```

- [ ] **Step 2: Verify JSON parses**

```bash
python -m json.tool .claude-plugin/plugin.json > /dev/null && echo "JSON OK"
```

Expected: `JSON OK`, exit 0.

- [ ] **Step 3: Final full-suite test run**

```bash
cd skills/image-to-web-design-chatgpt
python -m pytest tests/ -v
```

Expected: 10 PASS (7 vision_prep + 3 help).

- [ ] **Step 4: Commit**

```bash
git add .claude-plugin/plugin.json
git commit -m "feat(plugin): register image-to-web-design-chatgpt skill"
```

---

## Self-review checklist (for the implementer, after Task 8)

- [ ] All 10 tests pass.
- [ ] `git log` shows 8 commits (one per task).
- [ ] `skills/image-to-web-design-chatgpt/SKILL.md` is loaded by `Skill image-to-web-design-chatgpt` in a fresh Claude Code session (smoke-test the discovery).
- [ ] No file under the new skill folder imports from `../image-cut/`. Confirm with:
  ```bash
  grep -r "image-cut\|image_cut" skills/image-to-web-design-chatgpt/ || echo "clean"
  ```
  Expected: `clean`.

If any step above fails, do NOT mark the plan complete. Open a follow-up task describing the failure.
