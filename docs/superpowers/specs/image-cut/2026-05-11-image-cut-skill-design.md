# Image-Cut Skill — Design Spec

**Date:** 2026-05-11
**Status:** Draft, pending user review
**Skill location:** `~/.claude/skills/image-cut/`

## Purpose

Enable an AI agent that builds HTML pages from website screenshots to isolate
individual UI elements (icons, components, hero images, sections) as clean
image slices, with deterministic coordinate accuracy across crop / pad /
resize transforms.

Core problem: vision-model coordinate estimates on a full screenshot are
imprecise. The workflow zooms in on small regions to get accurate local
coordinates, then translates them back to the original image's pixel space to
make a final pixel-perfect cut from the full-resolution source.

## Workflow (what the skill teaches)

**Step 1 (always):** Agent estimates a rough bbox around the target element
and runs `crop.py` to produce a rough region.

**Step 2 — pick path by rough crop dimensions** (use `info.py` to check):

- **Eyeball path — rough crop ≤300×300 and vision-safe.**
  Agent looks at the rough crop directly, identifies the precise bbox in
  local coordinates, runs `translate.py` once on the rough receipt to get the
  global bbox.

- **Per-edge path — rough crop >300×300 (or eyeball cut wasn't accurate
  enough).**
  Agent crops 4 small probes (~100×100, or thin strips aligned to each edge)
  from the **original** screenshot, one centered on each edge of the rough
  bbox. Looks at each probe, identifies the precise edge pixel in local
  coordinates, translates each to global, assembles the precise bbox from
  the four edge values.

- **Non-vision-safe rough crop (long edge >1568px or portrait):** Resize the
  rough crop with `resize.py` to make it vision-safe before either path.
  Resize op extends the receipt chain so translation still composes
  correctly.

**Step 3 (always):** Final `crop.py` runs on the **original** screenshot
using the precise bbox. The rough crop and any probes are scaffolding; the
final asset is cut from the full-resolution source.

The eyeball path is the default attempt for small targets. Per-edge is the
precision fallback when eyeballing isn't accurate enough.

## Architecture

**Stack:** Python 3 + Pillow. No ImageMagick dependency. No external API calls.

**Layout:**
```
~/.claude/skills/image-cut/
├── SKILL.md         ← agent-facing workflow + tool reference
├── README.md        ← human reference
└── tools/
    ├── info.py
    ├── crop.py
    ├── pad.py
    ├── resize.py
    ├── convert.py
    └── translate.py
```

**Receipts:** every op that changes geometry writes a sidecar receipt at
`<output_path>.json` *and* echoes the same JSON to stdout. The agent reads
sidecars to chain transforms. `info.py` and `convert.py` do not produce
receipts (no geometric change).

**Receipt schema:**
```json
{
  "input":  {"path": "page.png",  "size": [1920, 1080]},
  "output": {"path": "slice.png", "size": [800, 600]},
  "op": {"op": "crop", "bbox": [120, 200, 920, 800]}
}
```

Each receipt records exactly one op. Chains are built by passing multiple
receipt files to `translate.py` in the order they were applied.

## Tools

### `info.py`

```
info.py INPUT
```

Prints JSON to stdout:
```json
{
  "path": "screenshot.png",
  "width": 1920,
  "height": 1080,
  "aspect": "16:9",
  "format": "PNG",
  "mode": "RGBA",
  "size_bytes": 482917,
  "vision_safe": true
}
```

`vision_safe` is true when the long edge is ≤1568px and width ≥ height
(landscape or square). Lets the agent decide eyeball vs per-edge vs
resize-first with a single call.

### `crop.py`

```
crop.py INPUT --bbox x1,y1,x2,y2 [--quality N=98] --out PATH
```

- Bbox is `x1,y1,x2,y2` in pixel coordinates of `INPUT`.
- No padding flags — for source-pixel context expand the bbox; for black
  margins use `pad.py`.
- `--quality` applies when `--out` is jpg/webp (default 98); ignored for png.
- Output format inferred from `--out` extension.

### `pad.py`

```
pad.py INPUT [--pad-top N] [--pad-right N] [--pad-bottom N] [--pad-left N]
             [--color #000000] [--quality N=98] --out PATH
```

- Each pad flag defaults to 0; at least one must be non-zero.
- `--color` sets the fill color (default black).
- Pad does not pull from source pixels — only adds margins. For including
  more source context around a region, expand the bbox in `crop.py`
  instead.

### `resize.py`

```
resize.py INPUT (--fit-width N | --fit-height N |
                 (--width N --height N) | --scale F)
              [--quality N=98] --out PATH
```

Mutually exclusive resize modes:
- `--fit-width N` — set width to N, scale height proportionally.
- `--fit-height N` — set height to N, scale width proportionally.
- `--width N --height N` — both required; explicit size, may distort.
- `--scale F` — multiply both dims by F.

No center-crop, no two-phase logic. To produce a square crop after a fit,
chain `resize.py` → `crop.py` with a computed centered bbox.

### `convert.py`

```
convert.py INPUT [--format webp|png|jpg] [--quality N=98] --out PATH
```

- `--format` defaults to `webp`.
- `--quality` defaults to 98 (applies to jpg/webp; ignored for png).
- Identity geometric transform — no receipt written.
- **Terminal op:** intended as the final step when converting format without
  geometric change. `crop.py`, `pad.py`, and `resize.py` already infer output
  format from `--out` extension, so format conversion mid-workflow happens
  inside those tools. `convert.py` exists for the "just reformat" case.
  Don't place `convert.py` in the middle of a geometric chain — its output
  has no receipt, which would break `translate.py` composition.

### `translate.py`

```
translate.py --chain R1.json [R2.json ...]
             (--point x,y | --bbox x1,y1,x2,y2)
             --to global|local
             [--round]
```

- `--chain` takes one or more receipt files in the order ops were applied
  (oldest first).
- `--to global` walks the chain backwards (each step maps local → input) to
  translate from the final transformed image back to the original's pixel
  space.
- `--to local` walks forwards (each step inverted) for the reverse direction.
- `--round` rounds outputs to nearest integer; default emits floats.
- Validates that `R[i+1].input.path == R[i].output.path`; mismatch is a
  fatal error citing the broken link.

**Per-op local → input map:**

| op | map |
|---|---|
| crop | `input_xy = local_xy + (bbox.x1, bbox.y1)` |
| pad | `input_xy = local_xy - (pad_left, pad_top)` |
| resize | `input_xy = local_xy * (in_w/out_w, in_h/out_h)` |

Bbox translation translates both corners independently, then sorts so
`x1 ≤ x2` and `y1 ≤ y2`.

## Edge cases

1. **Sub-pixel results from resize chains** — float by default; `--round`
   produces integers for cases needing exact pixels (final crop coordinates).
2. **Receipt chain mismatch** — `translate.py` exits with an error citing
   the broken link, preventing silent miscomposition.
3. **Crop bbox extending past image bounds** — `crop.py` exits with an
   error; agent must clamp the bbox first (using `info.py` dimensions).
   `pad.py` is the right tool for extending beyond source.
4. **Long edge >1568px after crop** — `info.py` reports `vision_safe: false`;
   agent runs `resize.py` before looking.

## Out of scope (explicit non-goals)

- ImageMagick integration (Pillow is sufficient and removes an install step).
- OpenAI / ChatGPT image API integration (out of scope; agent can pipe slice
  files to a separate tool later if needed).
- A standalone `vision_prep` tool (subsumed by `info.py` + `resize.py`).
- Center-crop or two-phase ops inside `resize.py` (composability via
  separate tools is preferred).
- Pad-during-crop (compose `crop.py` then `pad.py` instead).
- Single chained-ops CLI (separate tools fit the iterative agent loop
  better — eyeball and per-edge paths both call tools repeatedly).
- Interactive / GUI bounding-box selection (agent provides coords directly).

## Success criteria

- Agent can isolate any UI element from a website screenshot as a clean
  image slice cut from the original full-resolution source.
- Coordinate translation from a probe view back to global coords is
  deterministic and reproducible — no agent-side arithmetic.
- The six tools have ≤4 required flags each on the common path; the agent
  can recall them without consulting the skill mid-task once familiar.
- Receipts make every transform auditable: given a chain of JSON files, a
  human can verify the math by hand.
- Default outputs are webp at quality 98 — agent only specifies
  format/quality when overriding.
