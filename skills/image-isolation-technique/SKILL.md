---
name: image-isolation-technique
description: Recipes for extracting clean assets from a cropped region of an image — element track, background track, and outpaint. Use when an agent needs to isolate a component from its parent background, extract a continuous background patch under an overlay, or extend an image's canvas. Composes `image-edit-instruction` (AI edit primitive), `image-cut` (cropping), and `rembg` (alpha matting); introduces no new mechanisms.
---

# image-isolation-technique

> **Part of the [image-to-web-design](https://github.com/shimondoodkin/image-to-web-design) kit.**
> This skill composes [`image-edit-instruction`](../image-edit-instruction/SKILL.md)
> (the AI edit primitive) and [`image-cut`](../image-cut/SKILL.md) (cropping
> CLIs), and ships a supporting PIL snippet at
> [`_examples/outpaint_mask.py`](_examples/outpaint_mask.py). If you found
> this file on its own, the canonical kit has everything together —
> `npx skills add shimondoodkin/image-to-web-design`.

Recipes for working with a cropped piece of a design image. The skill assumes you have already used [`image-cut`](../image-cut/SKILL.md) (or any other cropper) to slice out the region you want to work on, and that you have access to the [`image-edit-instruction`](../image-edit-instruction/SKILL.md) primitive for the actual AI edits.

This is a recipe book, not a primitive. The agent reading it decides which recipe to apply, runs the steps, and looks at the results between calls. There is no internal loop and no automatic verification.

## Crop strategy

**Rule.** When the parent background is non-uniform (painted hero, photographic scene, gradient with detail), crop *loose* around the target — leave a generous margin of surrounding context. When the background is solid or flat, tight cropping is fine.

**Subject Verification Checklist:** Before executing any crop, check that the bounding box fully contains the target subject, component, or background details without clipping any elements (e.g., instrument bells, hats, fingers, outer borders). If any part of the subject is cut off, expand the bounding box to capture the subject in its entirety.

The reason: both downstream recipes (element track, background track) need to see the surrounding pixels in order to reason about texture continuity. A tight crop that runs flush against the target gives the editor nothing to extrapolate from, and the result will look pasted-in.

A safe default: include at least 20% extra space on each side of the target's bounding box. More if the parent has obvious large-scale texture (brush strokes, lighting gradients, foliage) that the editor will need to continue.

Do the actual cropping with [`image-cut`](../image-cut/SKILL.md)'s `crop.py` (or equivalent). This skill does not duplicate cropping mechanics — it just tells you how much to crop.

## Iterative isolation loop

The pattern for converging an image on what you want. Run by the agent, one call at a time, with a visual sniff-test between each call.

1. Identify the next element to remove. Use the order-of-removal heuristic below.
2. Write a locational instruction for `image-edit-instruction` (see that skill's Prompt conventions). One element per call.
3. Call `image-edit-instruction` with the current working image and the instruction. Save to the next numbered output file.
4. **Look at the result yourself.** Did the right thing get removed? Are there artifacts? Did anything else change?
5. Decide: continue with the next element, retry this step with a different instruction, swap backends, or stop.

### Order of removal (heuristic)

Peel elements off in this order, because each layer's removal depends on the surrounding pixels being intact:

1. **Foreground text** — titles, paragraphs, labels. Hard edges, easy fills.
2. **UI chrome** — buttons, badges, input fields, icons. Mostly geometric, easy fills.
3. **Decorative shapes** clearly separate from the painting — small swooshes, lines, dots.
4. **Subjects** — hero figures, products, characters, mascots. Bigger areas, harder fills; do these later.
5. **Leave the painted/illustrated background last.** It becomes your scalable background asset, or your input to further analysis.

### Stop signals

Stop trying to decompose when any of these happen:

- The background looks visibly worse after a removal (blur, fragmented texture, broken lighting).
- A "removal" introduces invented content (objects that weren't there) that you can't suppress with prompt tweaks.
- The element you wanted to remove turned out to be structurally fused with the painting (e.g. the badge is painted into the scene rather than overlaid).
- After two consecutive removals the working image is worse than the original.

When you hit a stop signal, accept the working image as-is and move to whatever's downstream (component synthesis, asset extraction, or a manual fix).

## Two-track extraction

The case that motivated this skill: a transparent component (button, badge, icon, character) sits on a non-uniform parent background, and you want **both** a clean asset for the component **and** a clean continuous background patch underneath it.

You don't pick one or the other. The same loose crop produces both, by running `image-edit-instruction` twice in parallel with different instructions.

### Element track

Goal: a clean cutout of the component on a flat field, ready for alpha matting.

Instruction template:

> Keep only the {component description} in the {position}. Replace everything else with solid white #FFFFFF.

Concrete example for a red "NEW" badge in the top right:

> Keep only the red "NEW" badge in the top-right corner around (1700, 90). Replace everything else with solid white #FFFFFF.

After the editor returns the flattened image, alpha-matte it with `rembg`. Install once: `pip install "rembg[cpu,cli]"` (or `[gpu,cli]`); the first run downloads the model.

**Prefer the library API over the CLI.** The `rembg` console script is not always on `PATH` (notebook / code-interpreter / ChatGPT sandboxes, minimal installs), and `python -m rembg` does **not** work (there is no `__main__`). The library always works once the base package is installed, lets you reuse one model session across many cutouts (load the model once — far faster), and trims the alpha in the same pass:

```python
from rembg import remove, new_session
from PIL import Image

session = new_session("birefnet-general")     # pick a model (see below); omit session= for the u2net default
cut = remove(Image.open("flattened.png"), session=session)   # returns RGBA
cut = cut.crop(cut.getbbox())                  # trim fully-transparent margins
cut.save("component.png")
```

CLI equivalent, when the console script *is* on `PATH`:

```bash
rembg i -m birefnet-general flattened.png component.png
```

**Model choice matters more than any flag:**

- `u2net` (default) — fine for a clean subject on a flat field (e.g. a chroma-keyed figure on solid green).
- `bria-rmbg` — strongest general matte for complex foregrounds (band members, hands, hair against busy backgrounds).
- `birefnet-general` — best for soft / painted edges (hair, fur, watercolour); slowest.
- `u2net_human_seg` / `isnet-general-use` — tuned for people / general objects respectively.

**Cleaner edges (optional):** turn on alpha matting — `remove(img, session=s, alpha_matting=True, alpha_matting_foreground_threshold=240, alpha_matting_background_threshold=10, alpha_matting_erode_size=10)` (CLI: `-a -ae 10`). It helps wispy edges but can nibble thin features, so look before trusting it.

**Always verify the matte:** composite the cutout over magenta and inspect the edges before shipping —

```python
bg = Image.new("RGBA", cut.size, (255, 0, 255, 255))
Image.alpha_composite(bg, cut).convert("RGB").save("component_check.png")
```

Reuse the one `session` for every subject in a batch.

The final asset is a transparent PNG of the component. Record the component's original position and size from the audit / bbox so downstream code can place it correctly.

### Background track

Goal: a continuous patch of the parent background where the component used to be.

Instruction template:

> Remove the {component description} in the {position}. Replace with a continuation of the surrounding painted texture only. Do not add new objects or text.

Concrete example for the same badge:

> Remove the red "NEW" badge in the top-right corner around (1700, 90). Replace with a continuation of the surrounding painted texture only. Do not add new objects or text.

The final asset is a clean continuous background patch. You can use it directly as the section background, sample it into a tile, or composite it into the parent.

### Parallelism

The two tracks are independent — they read the same source image and write to different outputs. Run them in parallel when the orchestrator supports it (e.g. two subagents from one Claude session, or two parallel CLI calls).

If you have multiple components to extract from one crop, the two tracks split per component, but the *background* track is sequential across components (each removal feeds the next). Element tracks across components remain parallel.

## Outpaint recipe

Extending a canvas is not a separate primitive — it is `image-edit-instruction` applied to a pre-padded image with a mask of the new padding region.

### Recipe

1. **Pad the source image to the target size and produce a white-over-padding mask** with the snippet at [`_examples/outpaint_mask.py`](_examples/outpaint_mask.py):

   ```python
   from PIL import Image

   def pad_and_make_mask(src, out_image, out_mask, target_size, anchor="center"):
       img = Image.open(src).convert("RGB")
       tw, th = target_size
       sw, sh = img.size
       assert tw >= sw and th >= sh

       if anchor == "center":
           ox, oy = (tw - sw) // 2, (th - sh) // 2
       elif anchor == "left":
           ox, oy = 0, (th - sh) // 2
       elif anchor == "right":
           ox, oy = tw - sw, (th - sh) // 2
       elif anchor == "top":
           ox, oy = (tw - sw) // 2, 0
       elif anchor == "bottom":
           ox, oy = (tw - sw) // 2, th - sh
       else:
           raise ValueError(f"unknown anchor: {anchor!r}")

       padded = Image.new("RGB", (tw, th), (255, 255, 255))
       padded.paste(img, (ox, oy))
       padded.save(out_image)

       mask = Image.new("L", (tw, th), 255)
       preserve = Image.new("L", (sw, sh), 0)
       mask.paste(preserve, (ox, oy))
       mask.save(out_mask)
   ```

   The reference copy at `_examples/outpaint_mask.py` is unit-tested; edit there and re-sync this skill if the snippet changes.

2. **Call `image-edit-instruction`** with the padded image, the mask, and an instruction such as:

   > Fill the white masked area with a natural continuation of the painting around it. Do not modify the unmasked area. Do not add new objects or text.

3. **Inspect the result.** The painted edges should blend into the new canvas without a visible seam. If you see a seam:
   - Try a softer mask boundary (a few pixels of grey on the inside of the white region).
   - Swap backend (gemini for painted/illustrative content; codex for photographic).
   - Accept the seam and feather it in code at compose time.

### When to outpaint

Only when you genuinely need a wider aspect ratio than the source provides — typically when the source is desktop-cropped and you need a portrait variant for mobile. Outpainting always introduces some uncertainty in the new region; if the source's aspect ratio is already close to what you need, scale rather than outpaint.
