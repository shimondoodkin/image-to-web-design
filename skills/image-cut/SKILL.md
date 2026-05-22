---
name: image-cut
description: Use when an agent needs to isolate UI elements (icons, components, hero images, sections) from a website screenshot as clean image slices for pixel-perfect HTML reconstruction. Provides high-level prep + points (recommended) and a low-level toolkit (crop, pad, resize, vision_prep, convert, translate) with deterministic coordinate translation.
---

# Image-Cut

> **Part of the [image-to-web-design](https://github.com/shimondoodkin/image-to-web-design) kit.**
> The CLI scripts this skill calls live in `tools/` next to this file. If
> you found this SKILL.md on its own (without `tools/`), the canonical kit
> has both together along with the sibling skills it composes with
> (`image-edit-instruction`, `image-isolation-technique`,
> `image-to-web-design`) — install with
> `npx skills add shimondoodkin/image-to-web-design`.

Tools for slicing website screenshots into pixel-perfect element images,
with reliable coordinate translation through Claude's vision pipeline.

## Why vision matters here

Per the Anthropic vision docs, Claude:

1. **Resizes** any image exceeding the model's limits to the largest size that
   fits, preserving aspect ratio.
2. **Pads** the result on the bottom/right to a multiple of **28 pixels**.
3. **Outputs coordinates** in this final resized+padded space. Clients must
   translate back.

### Claude family

| Model | Max long edge | Max tokens |
|---|---|---|
| `sonnet` / `opus-4.6` / `haiku` | 1568 | 1568 |
| `opus-4.7` | 2576 | 4784 |

Token formula: `width × height / 750`.

**Rescale trigger (empirically validated):** Claude internally rescales
when the SENT image's token count exceeds the cap, and returns coords in
the SCALED space (not the sent space). Validated by stress test:

| Sent (sonnet) | Over cap | Expected scale | Observed drift | Verdict |
|---|---|---|---|---|
| 1064² | under ✓ | 1.0 | ~2px noise | clean |
| 1084² (not 28-mult) | under ✓ | 1.0 | ~3px noise | clean |
| 1200² | 1.2× over | 0.904 | up to 113px | scaled |
| 1500² | 1.9× over | 0.723 | up to 431px | scaled |
| 2000² | 3.4× over | 0.542 | up to 718px | scaled |

The drift on over-cap inputs is **systematic, proportional to scale**, and
matches `sent_xy * expected_scale` to within a few pixels of visual noise.
Multiple-of-28 is irrelevant; only the token cap matters.

`vision_prep.py` and `prep.py` scale the image (downscale-only) to stay
under the cap and emit at the scaled size with no padding.

⚠️ **Avoid 1568×1568 with opus-4.7** — that specific size triggers an
internal rescale (122px systematic error observed in validation), even
though it appears under the 4784-token cap. The formula already avoids
it for normal inputs.

### Gemini family

Gemini accepts any image size at full coordinate accuracy — no padding
needed. Google charges by tile arrangement (N×M of 768×768 tiles where
N,M ∈ 1..3) regardless of whether the file is padded, so padding only
bloats the file.

- **Image fits within 2304×2304** → emitted at native size.
- **Exceeds 2304×2304** → downscaled to fit. No padding either way.

Pricing (informational):
- ≤384×384 → flat 258 tokens
- Otherwise: ⌈w/768⌉ × ⌈h/768⌉ × 258 tokens

Validation (gemini-3-flash-preview): **0px error at every size tested**
from 256² to 1064². Gemini is the most forgiving family for coord work.

`vision_prep.py` (and the high-level `prep.py`) **mirror each vendor's
pipeline client-side** — what you send is exactly what the model processes,
so coordinate translation has no hidden steps.

## Recommended workflow — `prep` + `points`

Two stateless commands. Pass the same `(ORIGINAL, region, padding, model)`
to both — no receipt files to track.

### Step 1 — prep the region you want to look at

```bash
python tools/prep.py screenshot.png \
    --region x1,y1,x2,y2 \
    --model sonnet \
    --out look.png
```

`look.png` is at the exact size Claude will process.

If you want margin around the region (so the element isn't right against the
edge), add per-side padding:

```bash
python tools/prep.py screenshot.png \
    --region 100,200,500,400 \
    --pad-top 20 --pad-right 20 --pad-bottom 20 --pad-left 20 \
    --out look.png
```

### Step 2 — look at `look.png` and note coordinates

Identify the precise points or corners you care about (in `look.png`'s pixel
space).

### Step 3 — translate back to original coords

```bash
python tools/points.py screenshot.png \
    --region 100,200,500,400 \
    --pad-top 20 --pad-right 20 --pad-bottom 20 --pad-left 20 \
    --points "lx1,ly1;lx2,ly2;lx3,ly3" \
    --round
```

Outputs `{"points": [[gx1, gy1], [gx2, gy2], [gx3, gy3]]}` — coordinates in
the **original** screenshot's pixel space.

**Important**: pass the same `--region`, padding flags, and `--model` to
`points.py` that you passed to `prep.py`. The math is re-derived; mismatched
inputs give wrong answers.

### Step 4 — final cut from the original

```bash
python tools/crop.py screenshot.png \
    --bbox X1,Y1,X2,Y2 \
    --out element.webp
```

Cut from the **original** screenshot, not from `look.png`. Defaults: webp at
quality 98.

## Precision strategies

- **Small target (≤300×300)**: prep once, eyeball the entire bbox in
  `look.png`, translate all four corners with `points.py` in one call.
- **Larger target / need pixel-perfect edges**: prep small probes around
  each edge of a rough bbox (~100×100 each), look at each probe, translate
  each probe's edge point to global. Assemble final bbox from translated
  values.

## Low-level toolkit (advanced)

If `prep`/`points` don't fit (e.g., custom transform chains, manual
composition), use the building blocks directly:

| Tool | Purpose | Receipt |
|---|---|---|
| `info.py` | Metadata + heuristic vision_safe check | No |
| `crop.py` | Crop by bbox | Yes |
| `pad.py` | Add per-side margins | Yes |
| `resize.py` | Fit / explicit / scale | Yes |
| `vision_prep.py` | Mirror Claude's pipeline (scale + 28-mult pad) | Yes |
| `convert.py` | Format conversion (terminal op) | No |
| `translate.py` | Map point/bbox across receipt chain | N/A |

Every geometric op writes a `<output>.json` receipt. Compose chains by
passing receipts (oldest first) to `translate.py`:

```bash
python tools/translate.py \
    --chain step1.png.json step2.png.json step3.png.json \
    --point x,y --to global --round
```

Chain validation: `step2.json.input.path` must equal `step1.json.output.path`.
`convert.py` is terminal — no receipt — don't place it mid-chain.

## Tips

- `--round` rounds output coords to ints (needed for `crop.py`).
- Bbox is always `x1,y1,x2,y2` with `x1 < x2` and `y1 < y2`.
- Output of `prep` is always padded to a multiple of 28 on each dim — that's
  intentional, matches Claude's internal padding so no double-pad.
- Use `--model opus-4.7` for higher-resolution work on Claude (3× more
  pixels available); costs more tokens.
- Use `--model gemini-3-flash` (or any gemini model) for the most accurate
  coords — validation showed 0px error at every tested size. Tile-based
  pricing: small images (≤384²) are flat-rate cheap.
- For `pad.py` color, use 3- or 6-digit hex: `#000`, `#ff8040`.
