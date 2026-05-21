# image-to-components

A small kit of agent-facing skills for converting design images into
pixel-perfect, responsive React webpages — and verifying the result against
the source.

## The four skills

The kit is organised as four layered skills with a strict downward dependency.
Each is a single SKILL.md with optional supporting tools and tests.

| Skill | Purpose |
|---|---|
| [`image-edit-instruction`](skills/image-edit-instruction/SKILL.md) | Atomic primitive: one AI-driven image edit call. Dispatches to Gemini/Codex native tools or to the codex/gemini CLI from Claude. |
| [`image-isolation-technique`](skills/image-isolation-technique/SKILL.md) | Recipes for extracting clean assets from a cropped region: iterative isolation, two-track element+background extraction, outpaint. |
| [`image-cut`](skills/image-cut/SKILL.md) | Python CLIs for cropping screenshots with reliable coordinate translation through each vendor's vision pipeline. |
| [`image-to-web-design`](skills/image-to-web-design/SKILL.md) | End-to-end orchestrator: design audit → region work → React synthesis → render → visual diff. |

Dependency direction (downward only):

```
image-to-web-design
  └── image-isolation-technique
        ├── image-edit-instruction
        └── image-cut
```

## Install

```bash
pip install -e .[dev]
```

Or just the runtime dependency:

```bash
pip install Pillow
```

## Tests

From the project root:

```bash
pytest
```

Pytest is configured in `pyproject.toml` to collect from both `tests/`
(outpaint snippet tests) and `skills/image-cut/tests/` (image-cut CLI tests).

## `image-cut` CLI reference

`image-cut` ships ten Python CLIs under `skills/image-cut/tools/`. They are
stateless: every geometric op writes a sidecar `<output>.json` receipt so
coordinate translation through Claude's or Gemini's vision pipeline stays
deterministic.

### High-level (recommended for agents)

Stateless — pass the same `(ORIGINAL, --region, padding, --model)` to both.

#### `prep.py`

```
prep.py ORIGINAL [--region x1,y1,x2,y2]
                 [--pad-top N --pad-right N --pad-bottom N --pad-left N]
                 [--model sonnet|opus-4.6|opus-4.7|haiku]
                 [--color #000000] [--quality N=98]
                 --out PATH
```

Crops the region (optional), pads (optional), then scales + pads to match
the chosen model's vision pipeline. Output is exactly what the model will
process — coordinates returned by the model map cleanly back.

#### `points.py`

```
points.py ORIGINAL [--region x1,y1,x2,y2]
                   [--pad-top N --pad-right N --pad-bottom N --pad-left N]
                   [--model sonnet|opus-4.6|opus-4.7|haiku]
                   --points "px,py;px,py;..."
                   [--round]
```

Translates a batch of points from prep-view coords back to the original
image's pixel space. Always translates "from prep view" → "to original".

### Low-level toolkit

#### `info.py`

```
info.py INPUT
```

Prints JSON: `path`, `width`, `height`, `aspect`, `format`, `mode`,
`size_bytes`, `vision_safe`.

`vision_safe` is a quick heuristic (long edge ≤1568, landscape). For
guaranteed model alignment, use `prep.py` or `vision_prep.py`.

#### `crop.py`

```
crop.py INPUT --bbox x1,y1,x2,y2 [--quality N=98] --out PATH
```

Bbox in pixel coords. Output format inferred from `--out` extension.
Rejects inverted or out-of-bounds bboxes.

#### `pad.py`

```
pad.py INPUT [--pad-top N] [--pad-right N] [--pad-bottom N] [--pad-left N]
             [--color #000000] [--quality N=98] --out PATH
```

Adds margins outside source pixels. At least one pad value must be > 0.

#### `resize.py`

```
resize.py INPUT (--fit-width N | --fit-height N |
                 (--width N --height N) | --scale F)
              [--quality N=98] --out PATH
```

Mutually exclusive resize modes. `--width` and `--height` must be used
together (explicit, may distort). Others preserve aspect.

#### `vision_prep.py`

```
vision_prep.py INPUT [--model sonnet|opus-4.6|opus-4.7|haiku]
                     [--color #000000] [--quality N=98] --out PATH
```

Mirrors each vendor's vision pipeline so the image you send is exactly
what the model processes. Source content stays aligned at (0, 0).

**Claude family** (sonnet / opus-4.6 / opus-4.7 / haiku):
- Downscale-only, preserving aspect, so the sent image satisfies
  `max(w, h) ≤ max_long_edge` AND `w * h ≤ max_tokens * 750`.
- No client-side padding (multiple-of-28 alignment isn't required —
  validated empirically; see `docs/research/`).

| Model | Max long edge | Max tokens |
|---|---|---|
| `sonnet` / `opus-4.6` / `haiku` | 1568 | 1568 |
| `opus-4.7` | 2576 | 4784 |

**Gemini family** (gemini-3-flash, gemini-3.1-pro, gemini-2.5-*, etc.):
- Native-size pass-through up to 2304×2304 — Gemini handles any size at
  full coordinate accuracy, no padding needed.
- Larger → downscaled to fit 2304×2304 (preserves aspect).
- Pricing: tiled at 768×768 (1..3 each axis), 258 tokens per tile;
  ≤384² is a flat 258-token rate.

#### `convert.py`

```
convert.py INPUT [--format webp|png|jpg] [--quality N=98] --out PATH
```

Format conversion only — no geometric change, no receipt. Default webp q=98.

#### `translate.py`

```
translate.py --chain R1.json [R2.json ...]
             (--point x,y | --bbox x1,y1,x2,y2)
             --to global|local
             [--round]
```

Translate across a chain of receipts.

### Receipt format

Geometric ops (`crop`, `pad`, `resize`, `vision_prep`) write `<output>.json`:

```json
{
  "input":  {"path": "page.png",  "size": [1920, 1080]},
  "output": {"path": "slice.png", "size": [800, 600]},
  "op": {"op": "crop", "bbox": [120, 200, 920, 800]}
}
```

The `op` object varies by tool:

- `crop`: `{"op": "crop", "bbox": [x1, y1, x2, y2]}`
- `pad`: `{"op": "pad", "pad": {...}, "color": "#rrggbb"}`
- `resize`: `{"op": "resize", "mode": "...", "in_size": [...], "out_size": [...]}`
- `vision_prep`: `{"op": "vision_prep", "model": "sonnet", "scale": F, "scaled_size": [...], "padded_size": [...], "color": "#rrggbb"}`

## Repository layout

```
image-to-components/
├── pyproject.toml
├── README.md                  ← this file
├── skills/
│   ├── image-edit-instruction/SKILL.md
│   ├── image-isolation-technique/
│   │   ├── SKILL.md
│   │   └── _examples/outpaint_mask.py      # tested PIL snippet for outpaint masks
│   ├── image-cut/
│   │   ├── SKILL.md
│   │   ├── tools/                          # 10 Python CLIs
│   │   ├── scripts/                        # research scripts that produced docs/research/
│   │   └── tests/                          # 80 tests covering the CLIs
│   └── image-to-web-design/SKILL.md
├── tests/                                  # outpaint snippet tests (3)
├── docs/
│   ├── research/                           # validation reports backing image-cut's claims
│   └── superpowers/
│       ├── specs/                          # design specs (this kit + image-cut history)
│       └── plans/                          # implementation plans
```

`skills/image-cut/scripts/` contains the research code that produced
`docs/research/2026-05-12-vision-validation-report.md`. Keep them together;
they're the reproducibility trail for the vision-pipeline numbers in
`vision_prep.py`.
