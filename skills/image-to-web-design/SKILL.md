---
name: image-to-web-design
description: End-to-end conversion of a design image into a React webpage with visual comparison against the source. Use when an agent receives a screenshot, mockup, or painted reference and needs to produce HTML/JSX/Tailwind that closely matches the image, render the result, and iteratively close the visual gap. Orchestrates `image-cut` (slicing), `image-isolation-technique` (asset extraction), React synthesis, headless rendering, and vision-LLM diffing.
---

# image-to-web-design

> **Part of the [image-to-web-design](https://github.com/shimondoodkin/image-to-web-design) kit.**
> This orchestrator defers all pixel work to
> [`image-isolation-technique`](../image-isolation-technique/SKILL.md)
> (which in turn calls [`image-edit-instruction`](../image-edit-instruction/SKILL.md))
> and all cropping to [`image-cut`](../image-cut/SKILL.md). If you found
> this file on its own, install the full kit so the recipes referenced
> below resolve — `npx skills add shimondoodkin/image-to-web-design`.

End-to-end pipeline: design image in → rendered React webpage out, with a visual-diff loop to close the gap. This skill is the orchestrator. It defers all pixel-level work to [`image-isolation-technique`](../image-isolation-technique/SKILL.md) (which in turn defers to [`image-edit-instruction`](../image-edit-instruction/SKILL.md)) and all cropping to [`image-cut`](../image-cut/SKILL.md).

The stages are in order. Each stage's output feeds the next; sniff-test visually between stages and stop early if a stage produces something that won't survive the next one.

## Load the full kit FIRST — before stage 1

> [!IMPORTANT]
> This file is **orchestration only**. Every how-to detail — cropping, coordinate math, the removal loop, two-track extraction, outpaint, seam/colour matching, the AI-edit primitive and its backends — lives in the sibling skills. **Read all of them up front, before you crop a single pixel.**
>
> Do **not** lazy-load them one stage at a time. Lazy-loading is the single biggest cause of steps executed with the wrong technique (observed in real runs: a section was cropped too tight, a subject isolated without the green-screen+rembg recipe, seams left mismatched — all because the relevant sub-skill hadn't been read yet).

Invoke/read every sibling skill now, in this order, and keep them in context for the whole job:

1. [`image-cut`](../image-cut/SKILL.md) — slicing screenshots, vision-safe sizing, translating coordinates back to the original.
2. [`image-isolation-technique`](../image-isolation-technique/SKILL.md) — the iterative removal loop, two-track (element + background) extraction, the outpaint recipe, and the colour/seam-matching tricks.
3. [`image-edit-instruction`](../image-edit-instruction/SKILL.md) — the one AI-edit primitive and backend selection (`codex-imagegen` / `codex` / `gemini`).

If any reference fails to resolve, the kit isn't fully installed — run `npx skills add shimondoodkin/image-to-web-design` and re-read before continuing. Only once all four skills (this one + the three above) are in context do you start the audit.

## Design audit / element inventory

Before touching pixels, ask a vision LLM to produce a structured inventory of every element in the source. The inventory becomes both the removal plan (for the isolation skill) and the component spec (for synthesis).

Save the result as `audit.json` in the working directory.

### JSON shape

```json
{
  "viewport": {"width": 1920, "height": 1080},
  "sections": [
    {
      "name": "hero",
      "bbox": [0, 0, 1920, 720],
      "background": {"kind": "painted_illustration", "dominant_colors": ["#2b3a55", "#d4a76a"]},
      "container": {
        "padding": {"top": 120, "right": 80, "bottom": 80, "left": 120},
        "content_max_width": 600,
        "vertical_alignment": "center"
      },
      "layout_kind": "flex_column",
      "elements": [
        {"id": "title",       "kind": "text",     "bbox": [120, 220, 900, 320],  "content": "Welcome to ...", "approx_size_px": 64, "weight": "bold"},
        {"id": "subtitle",    "kind": "text",     "bbox": [120, 340, 800, 400],  "content": "...",            "approx_size_px": 22},
        {"id": "cta_button",  "kind": "button",   "bbox": [120, 440, 320, 500],  "label": "Get started",      "fill": "#d4a76a", "padding": {"x": 24, "y": 12}},
        {"id": "badge_new",   "kind": "badge",    "bbox": [1600, 60, 1800, 120], "label": "NEW",              "fill": "#e84a4a"},
        {"id": "hero_figure", "kind": "subject",  "bbox": [900, 120, 1500, 700], "note": "painted character; extract as transparent PNG", "edge_quality": "soft"}
      ],
      "gaps": [
        {"between": ["title", "subtitle"],     "px": 20},
        {"between": ["subtitle", "cta_button"], "px": 40}
      ]
    }
  ]
}
```

### Rules

- **Element `kind` decides downstream treatment.** `text`, `button`, `badge`, `icon` are rebuilt entirely in code. `subject` is both extracted as a transparent PNG **and** removed from the background (two-track extraction in image-isolation-technique). Ambiguous shapes are marked `decoration_likely_background` and left in the painting unless removal makes the layout cleaner.
- **No auto-detection of a base spacing unit.** Capture gaps as measured. At synthesis time, snap them to a small set of values by eye (typically multiples of 4 or 8).
- **Approximate colours and sizes are good enough for the first draft.** Refine after the first render-and-compare round.

The audit is the spec. Every element becomes either a JSX element, a positioned asset, or part of the background.

## Region work

For each section in the audit, do the per-section pipeline:

1. **Crop the section** out of the source with [`image-cut`](../image-cut/SKILL.md) using the section's `bbox`. Save as `<section>/00_original.png`.
2. **Identify overlay elements** in the section that need extracting (subjects, badges, custom-shape decorations).
3. **For each overlay element on a non-uniform background**, run the two-track extraction recipe from `image-isolation-technique`:
   - Element track → transparent PNG asset under `<section>/assets/`.
   - Background track → updated working background under `<section>/NN_no_<element>.png`.
4. **For each overlay element on a uniform/solid background**, you may skip the dual extraction and just remove the element (single track) — the background continuation is trivial.
5. **For text, buttons, badges, icons**, remove them from the background only (these are rebuilt in code; no element track needed). Run iterative isolation per `image-isolation-technique`.

At the end of region work you have, per section:
- A clean painted background with all rebuilt-in-code elements removed.
- One transparent PNG per subject / custom-shape asset, with position metadata recorded from the audit bbox.
- For backgrounds whose pattern is solid, gradient, or cleanly tileable, the audit colour information is enough — no image asset needed. For unified paintings, ship the cleaned background as a single asset.

The how-to-isolate detail (instruction templates, crop margin, mask choice, retry rules) lives in `image-isolation-technique`. This section gives orchestration only.

## React synthesis

Default stack: **TypeScript + Tailwind**. Adjust if the user's project has a different convention.

### Layout primitives

The audit's `layout_kind` per section picks the primitive:

- `flex_column` → flex container with `gap-N` between siblings.
- `flex_row` → flex container with `gap-N` and an alignment.
- `grid` → grid container with `gap-N` and a column count.
- `overlay` (mark explicitly) → absolute positioning of a decorative element over a flex/grid parent.

**Absolute positioning is reserved for decorative overlays only** — corner badges, callouts, characters floating over a card. Never use absolute positioning for primary content flow. If the audit says `flex_column`, the title / subtitle / CTA are flex children with `gap-N`, not absolutely positioned siblings. This is the single biggest difference between image-to-code that looks like a real component and image-to-code that looks like a flat screenshot.

### Padding vs. gap

- Container `padding` from the audit goes on the section wrapper.
- Inter-element `gaps` go on the flex/grid parent as `gap-N`.
- Element `padding` (a button's interior spacing) goes on that element.
- Don't fake `gap` with `mt-N` on every sibling — use the parent's `gap-N` once.

### Backgrounds

- A unified painting → `bg-[url(...)]` arbitrary value on a styled div, with `bg-cover bg-center` or equivalent.
- A solid colour → `bg-[#xxxxxx]`.
- A gradient that looks tileable or gradient-y → emit CSS (`linear-gradient`, `radial-gradient`) instead of an image asset. This is the best outcome and should be preferred whenever the background is approximately one of these patterns.
- A tileable pattern → extract the smallest seamless tile and use `background-repeat: repeat`.

Backgrounds go on a styled div, not on an `<img>` tag.

### Text

Text is text. Never bake text into an image asset — the user wanted "text aligned to centre with a badge," not "screenshot with painted-on text." Use the audit's content, approximate size, and weight as the first draft; refine after the first compare.

### Responsive variants

Three escalating mechanisms:

- **Resolution variants only** (same image, different pixel densities) → `srcset`.
- **Same composition, CSS handles the rest** → single asset, with `object-fit` / `object-position` / `bg-position` changes at breakpoints.
- **Art-directed swap** (different crop or entirely different image per breakpoint) → `<picture>` with one `<source>` per breakpoint. Each `<source>` points at a fully separate asset, produced by running the region-work pipeline on that breakpoint's source image.

If the design has heavy art-directed mobile (subject offset right at 60% width on desktop, centred at 90% on mobile), run the audit + region work on the mobile source separately.

### Component file layout

```
components/
  Hero/
    Hero.tsx
    assets/
      hero-bg.png             # cleaned painted background from region work
      hero-figure.png         # transparent subject from two-track extraction
      hero-figure@2x.png      # if a retina variant exists
      badge-new.svg           # if the badge was traced to SVG
```

If a section needs art-directed mobile, add `*-mobile.png` siblings and emit `<picture>`.

## Render and visually compare

After synthesis, render the React component to PNG at the same resolution as the source and diff.

### Render

Headless Chromium via Playwright is the default; any equivalent (`npx tsx render.tsx`, Puppeteer) works. Render at the source viewport (`1920×720` for desktop, `375×667` for mobile, etc.).

### Two diff signals

1. **Numeric (catches regressions, optional).** LPIPS or SSIM at per-section resolution. Useful for detecting that an iteration made things visibly worse. No mandatory threshold — what counts as "good enough" depends on whether the design is painted (looser) or flat-CSS (tighter).

2. **Semantic (tells the agent what to fix).** Vision-LLM diff with this prompt:

   > Here are two images: the original design (left) and a rebuilt React component (right). List the differences in design terms — position, size, colour, spacing, typography. For spacing specifically, report gaps between sibling elements that differ noticeably, container padding mismatches, and inconsistent rhythm. Order findings by visual impact. Ignore differences smaller than 4px.

Apply the semantic findings by hand: tweak the JSX, re-render, re-diff. Two or three rounds is normal.

## When to stop

Stop refining when any of these hold:

- The semantic diff returns no items above the "noticeable" bar.
- Remaining diffs are inherent to rendering (subpixel font differences, anti-alias variance) and not fixable.
- You've done three rounds and remaining diffs are stable — further iteration is overfitting.

**Also stop if decomposing damages the source.** If the painting is unified and removing an element distorts neighbouring areas (faces warped, textures fragmented, lighting broken), use the original image whole as a single `background-image: cover` asset and layer text/buttons on top. This is a valid outcome, not a failure.

Signs you've crossed the damage line:
- Inpainting introduces visible blur or invents content.
- After two removals the background looks worse than before.
- The "decorative" element turns out to be structural in the painting.

## Working directory layout

Per design, a single working directory holds everything:

```
<workdir>/
  source.png                  # original input
  audit.json                  # design audit
  hero/
    00_original.png           # cropped section
    01_no_title.png           # after removing title
    02_no_button.png
    ...
    99_clean_background.png   # final cleaned background
    masks/
      title.png
      badge.png
    assets/
      hero_figure.png         # transparent subject
      hero_figure.json        # subject position metadata
  components/
    Hero/
      Hero.tsx
      assets/                 # final assets imported by the component
  comparisons/
    iter-1.png                # diff visualisation
    iter-1-report.md          # numeric + semantic results
```

Numbered, never overwritten. Anyone (human or agent) can walk the directory and sniff-test the pipeline by opening files in order.

## Field notes (lessons from real builds)

Hard-won specifics from actual runs. Each is **symptom → what to do**. They apply whether you synthesize React/Tailwind or plain HTML+CSS — the kit defaults to React but the pixel + layout techniques are framework-neutral.

### Cropping & measuring the source

- **One mockup often contains several viewports** (a phone and a desktop side by side, with "MOBILE FIRST" / "DESKTOP" annotation labels). Split them into separate source images *first*, and drop the annotation labels from the crop. Treat each as its own audit + region-work pass.
- **Measure seams with a tall, full-height probe, not short strips.** Short wide strips at 1:1 misread horizontal boundaries badly (a phone's right edge read ~190px on a short strip but ~365px on a tall one — the tall one was right). When a coordinate looks surprising, re-probe with a column that spans the full height of the region.
- **Crop the whole section to its natural boundary, not a tight sub-box.** Isolating a "hero background" by cropping only the hero sliced the festive art in half. Crop down to where the art actually fades to white / the next section begins. The user's phrase "the *top part*, not the hero" means exactly this.

### The edit backend redraws wholesale

- **Backend used: the `codex-imagegen` command** — a standalone skill that posts directly to the ChatGPT-Codex image endpoint reusing Codex's OAuth (`~/.codex/auth.json`, no `OPENAI_API_KEY`): `python scripts/imagegen.py edit --image in.png [--image ref.png] [--mask m.png] --size WxH --out out.png --prompt "…"` (also `generate` / `generate-batch`). It is the concrete realization of `image-edit-instruction` for a Claude agent; see that skill for backend selection. The caveats below are its behaviour.
- **The hosted image-edit tool (codex / gpt-image) regenerates the entire image**, it does not do true masked inpaint. Consequences:
  - For "keep only the subject, solid green everywhere else" isolation, *and* for fixing content (a detached/duplicated instrument, a wrong hand) — do both in **one** prompt; it's all one redraw anyway.
  - To fix a shape **cut off at an edge**, don't bother with a mask + outpaint — just regenerate with `"keep a clean margin along the {edge}; every shape fully rounded and contained; nothing touching the {edge}"`. More reliable than masked outpaint here.
- **Aspect-ratio is limited.** Extreme ratios are rejected (`image_generation_user_error / invalid_value`): ~4:1 (e.g. `1792x416`) failed; `2048x1024` (2:1) worked; `2048x720` (~2.84:1) worked. For wide banners stay ≲ 2.85:1, or generate at 2:1 and crop. Generate big, then post-process (resize/recolor/pad) with PIL.

### Subjects: chroma-key, then rembg

- Isolate a subject by asking for it on **solid bright green (#00B140)** with everything else replaced by green, then `rembg` → transparent PNG, then trim to `getbbox()`. Green both reads as "isolate this" to the model and gives `rembg` a clean matte. Composite the result over magenta to eyeball the alpha edges before shipping.

### Colour continuity is the thing that breaks first

- **Section "whites" must be made equal, not assumed.** Generated art's white is ~`(254,254,254)`, *not* pure `#fff` and *not* a surface tint like `#FAFAFC`. Mismatched whites show as a visible band where an image area meets a CSS-coloured area. Fix: sample the art's white with PIL and set the page/section background to that exact value; prefer making the inner sections `background: transparent` and letting one shared wrapper colour show through.
- **A "connector" colour (a wave/strip baked into one image that must merge into an adjacent solid section) will not match by luck.** Sample both with PIL; recolour the baked strip to the section's exact colour (`if max(r,g,b) < 46: px = TARGET`) so the seam disappears. Then set the adjacent CSS section to the *same* literal value.

### Aligning a background to a content edge

- **To make a background end exactly at a content boundary (bottom of the subject / top of the title), put the background on a wrapper sized to that content** — not on a width-scaled layer. `background-size: 100% auto` makes the art's height track the *viewport width*, so the bottom edge lands in a different place at every breakpoint. A wrapper whose height is its content pins the edge consistently.
- **To show a banner fully with no crop and no distortion**, generate the art at the display box's aspect ratio and give the box that same `aspect-ratio` with `background-size: 100% 100%` (no distortion *because* the ratios match). `cover` crops; `contain` letterboxes.

### Page-level background wrappers

- For full-bleed art that must run continuously behind several sections, wrap them: a **top-bg wrapper** (festive art, `background-position: top`) around header+hero+features, and a **bottom-bg wrapper** (dark, `background-position: bottom`) around CTA+footer. Make the inner sections transparent so they read through. Opaque inner sections (cards, light panels) still cover the wrapper where needed.
- Scope a per-element background to the element, not the wrapper, when only that element should carry it (e.g. a CTA's colourful art) — otherwise it "engulfs" neighbours or peeks out between them.

### RTL gotchas

- **Logical properties flip under `dir="rtl"`.** `inset-inline-start` became the *right* side. Use physical `left`/`right` when matching a specific visual side of the mockup.
- Put `direction: ltr` on a header row to keep brand-left / CTA-right while leaving the nav's Hebrew text `direction: rtl`. Use `order` / `margin-inline-start: auto` to pin row icons to the correct edge.

### Trust the mockup's pixels over the design-system doc

- The written spec said "CTA = pink→purple gradient", but the *rendered* mockup used a **flat pink `#F4255C`**, and social glyphs were **dark on light circles**, not brand-pink. Eyedrop the mockup for real colours; the doc is aspirational.

### Art-directed mobile is its own isolation pass

- The mobile hero was a *different* composition (a full band photo vs. a desktop trio, a centred logo, its own leaf decoration). Crop + isolate on the mobile source separately, then swap via media queries / `<picture>`. Don't try to reuse the desktop assets.

### Overlapping a scaled element (logo over a photo)

- To overlap a logo over a photo, keep it centred, and have it scale with the viewport: absolutely position it (`left:50%; transform: translateX(-50%); top: …`) over a wrapper given `position: relative` and a `padding-top` that reserves the space; size it with `width: clamp(min, ~46vw, max)` so it stays proportional and centred at every width.

### Loop in the browser at several widths

- Render and screenshot at desktop **and** multiple phone widths (e.g. 390 and 600). Band gaps, colour seams, cut edges, RTL flips, and "logo too small/high when wider" only reveal themselves at specific widths. Serve the folder (`python -m http.server`) and drive it headless to iterate.

## Out of scope

Spelled out so the agent doesn't drift:

- Interactive states (hover/focus/active), motion / animation, form behaviour, state management, API integration — out of scope. The visual rendering is the goal.
- Accessibility states beyond basic semantic HTML and `alt` text — out of scope.
- Pixel-perfect font matching when the source uses a proprietary font without a known web equivalent — choose the nearest web font and flag the substitution.

If the user wants any of the above, treat it as a follow-up task with its own goals.
