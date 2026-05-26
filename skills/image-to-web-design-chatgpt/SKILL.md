---
name: image-to-web-design-chatgpt
description: "Use when ChatGPT receives a design image (screenshot, mockup, or painted reference) and needs to produce HTML/JSX/Tailwind that closely matches the source. Self-contained end-to-end pipeline tuned for ChatGPT: native image gen for asset isolation, rembg in the code interpreter for alpha matting, and the 768 px shortest-side vision rule for accurate audits."
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

If `tools/vision_prep.py` isn't available, paste this into your code interpreter — it does the same OpenAI vision_prep without the unsharp-mask polish (coordinates round-trip within ≤1 px of the CLI version):

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
