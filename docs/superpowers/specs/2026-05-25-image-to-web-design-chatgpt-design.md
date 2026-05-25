# image-to-web-design-chatgpt — design spec

**Date:** 2026-05-25
**Status:** Brainstormed and approved; ready for implementation plan.
**Goal:** A single, self-contained skill that gets ChatGPT from a design
image to a JSX/Tailwind component without ever telling it to invoke
codex, gemini headless, or any other agent-specific CLI.

## Why

The kit already has four primitives: `image-cut`,
`image-edit-instruction`, `image-isolation-technique`, and
`image-to-web-design`. They were factored to deduplicate prose. But:

- AI agents do not reliably read sibling skills. Each agent loads the
  one it was pointed at.
- The four-skill version of `image-edit-instruction` documents codex
  and gemini headless invocations as editing primitives. When ChatGPT
  was pointed at this kit, it tried to invoke those commands — they do
  not apply to it.
- Each agent has a different capability profile: ChatGPT has strong
  native image generation but vision degrades above ~768 px; Claude
  has good vision but cannot generate images; Gemini has good vision
  but its native image edit (nano-banana) often stretches or extends
  the source instead of editing it.

The fix is one self-contained skill per agent. This spec covers the
ChatGPT skill only. Claude and Gemini variants follow the same pattern
in later specs.

## Scope

- **In scope:** the full image → React pipeline for ChatGPT: audit,
  slice, isolate assets, synthesise JSX/Tailwind, visual diff.
- **Out of scope:** Claude and Gemini variants; reorganising the
  existing four-skill folder structure; removing the umbrella
  `image-to-web-design` skill.

## Location and structure

```
skills/image-to-web-design-chatgpt/
  SKILL.md
  tools/
    vision_prep.py     # OpenAI-only, no --model flag
    crop.py            # bbox crop, verbatim from image-cut
    translate.py       # 768-space ↔ source coords, OpenAI branch only
```

The folder is self-contained. It does **not** import from
`../image-cut/`. Cost: minor code duplication of `crop.py` and the
OpenAI branch of `translate.py`. Benefit: the user can point ChatGPT
at this one folder without coupling to siblings.

## Frontmatter

```yaml
---
name: image-to-web-design-chatgpt
description: Use when ChatGPT receives a design image (screenshot, mockup, or painted reference) and needs to produce HTML/JSX/Tailwind that closely matches the source. Self-contained end-to-end pipeline tuned for ChatGPT: native image gen for asset isolation, rembg in the code interpreter for alpha matting, and the 768 px shortest-side vision rule for accurate audits.
---
```

The description names the three primitives ChatGPT uses (native image
gen, rembg in the sandbox, 768 px vision rule) so the skill router can
pick it. It does **not** list what ChatGPT must avoid. The skill simply
omits codex/gemini-only material. Negative framing is known to confuse
editors (the same principle the kit already applies to image-edit
prompts).

## SKILL.md section list

1. **What this skill does.** One paragraph framing: receive a design
   image, end with a JSX/Tailwind component plus extracted assets.
2. **ChatGPT's toolset.** The three primitives (vision at 768 px,
   native image gen, code interpreter with PIL + rembg) and the
   routing rule between them.
3. **Audit the source image.** How to look at it under the 768 px
   rule, what to list (elements, colours in hex, positions in source
   space, fonts).
4. **Slice the image.** Use `tools/crop.py` then `tools/vision_prep.py`
   in the code interpreter. Coordinate translation rule.
5. **Isolate assets with native image gen.** Element-track and
   background-track recipes. Element track is two-step: native image
   gen flattens the subject onto solid white, then `rembg` runs in
   the sandbox for clean alpha.
6. **Synthesise JSX/Tailwind.** Component shape, asset embedding,
   typography, colour, layout-drift fix.
7. **Visual diff.** Render the result and compare against the source.
   Default path is user-driven; playwright-in-sandbox is the "if you
   can" path.
8. **Stop signals.** When to accept the current draft.

Sections 4, 5, and 6 are the bulk. The others are short.

## Section detail

### §2 — ChatGPT's toolset

Positively framed. The whole section is roughly:

> You have three primitives.
>
> **1. Vision at 768 px shortest-side.** OpenAI's vision pipeline
> (detail:high) scales any image to fit 2048×2048, then scales again
> so the shortest side is 768 px. The processed image is what you
> actually see. Send a square at 768×768 and you skip both rescales —
> coordinates round-trip with under 1.4 px noise (validated in
> `docs/research/2026-05-12-vision-validation-report.md`). For
> non-square images, target shortest-side = 768. Use
> `tools/vision_prep.py` to do this mechanically.
>
> **2. Native image generation for editing.** When you need to remove,
> isolate, or fill an area, use your built-in image edit. Give it a
> locational instruction and let it produce the edited image. Do not
> write a Python script that synthesises the edit — the native tool
> does it in one call.
>
> **3. Code interpreter for deterministic work.** Cropping, padding,
> resizing, coordinate translation, alpha matting with `rembg`,
> side-by-side diffing — Python sandbox. PIL is available; `rembg` can
> be installed with `pip install "rembg[cpu,cli]"` on first use.
>
> **Routing rule.** Visual and creative (paint over, fill, remove) →
> native image gen. Deterministic and geometric (crop these pixels,
> resize to N) → code interpreter. The two-step element-isolation
> recipe (flatten with image gen → alpha-matte with rembg) uses both
> in sequence; that pattern is in §5.

### §4 — Slice the image

Three sub-parts:

1. **The mechanic.** A short example showing `tools/crop.py` followed
   by `tools/vision_prep.py` in the sandbox, output is at 768 px
   shortest side.
2. **Inline fallback.** A roughly 30-line Python block that does the same
   vision_prep operation without depending on `tools/vision_prep.py`.
   Documented as "use the file if you have it, this block if you
   don't." Same recipe, no `--model` flag because there is only one
   model family.
3. **Coordinate translation.** When ChatGPT reads a coordinate off the
   768-space image, multiply by `source_long_edge / 768` (after
   accounting for the 2048-fit stage if the source was over 2048).
   `tools/translate.py` does this. Inline fallback covers it in two
   lines.

### §5 — Isolate assets with native image gen

Two recipes, both from `image-isolation-technique` but rewritten to
use ChatGPT's native edit rather than codex or gemini headless calls.

**Element track (the two-step recipe):**

1. Native image gen with a locational instruction:
   > Keep only the {component description} in the {position}. Replace
   > everything else with solid white #FFFFFF.
2. In the code interpreter, run `rembg i flattened.png component.png`
   for clean alpha. For complex foregrounds use
   `rembg i -m bria-rmbg flattened.png component.png`; for
   soft-edged subjects use `rembg i -m birefnet-general …`.

**Background track:**

> Remove the {component description} in the {position}. Replace with a
> continuation of the surrounding painted texture only. Do not add new
> objects or text.

No "Do not modify the X itself" tail. The omission matches the
"avoid negative preservation constraints" rule already established
in the kit.

### §6 — Synthesise JSX/Tailwind

- **Component shape.** One React function component per visually
  distinct section (hero, nav, card grid). Tailwind utility classes
  for layout/spacing; raw CSS only when Tailwind cannot express the
  thing.
- **Asset embedding.** Isolated assets from §5 go in `public/` and are
  referenced by path. Absolute coords from the §3 audit translate to
  Tailwind position utilities (`absolute top-[90px] right-[24px]`).
- **Typography.** Audit reports font family + size; component uses
  Tailwind `font-` / `text-[Npx]` arbitrary values when no near match
  exists.
- **Colour.** Audit reports hex; component uses Tailwind arbitrary
  values (`bg-[#a73c2f]`) — no theme extension for one-off projects.
- **Layout-drift fix.** If a region is misaligned after rendering,
  re-audit that specific region under the 768 px rule and adjust the
  offsets. Do not eyeball.

### §7 — Visual diff

- **Default path:** user runs the React component (`npm run dev` or
  equivalent), screenshots the page, uploads the screenshot back to
  ChatGPT. ChatGPT compares both images under the 768 px rule and
  reports the largest concrete differences (offset, colour, missing
  element).
- **"If you can" path:** if `playwright` is installable in the
  sandbox, render the React build to PNG, side-by-side via PIL, diff
  the largest deltas without a round-trip through the user.

Iterate by listing concrete differences and adjusting the component
code. Stop signals are in §8.

### §8 — Stop signals

Accept the current draft and stop iterating when any of:

- The largest pixel-level offset is under the threshold the user
  named at the start (or 8 px if no threshold was given).
- Two consecutive iterations changed the rendered output by less than
  one visual element each.
- The remaining differences are in areas the user already accepted
  earlier in the conversation.

## Things this spec deliberately does NOT do

- Does **not** add an OpenAI family to the existing
  `skills/image-cut/tools/vision_prep.py`. That sibling tool stays
  unchanged. The new skill's `tools/vision_prep.py` is OpenAI-only.
- Does **not** modify the existing four skill folders. They keep
  working for Claude users in Claude Code.
- Does **not** modify any existing skill source file. The only
  outside-the-new-folder change is one line in `.claude-plugin/plugin.json`
  to add the new skill path to its explicit `skills` whitelist (the
  manifest enumerates skills rather than auto-discovering, so a new
  folder alone is not enough).

## Open items for the implementation plan

The implementation plan (next step) needs to resolve:

- Exact content of the inline-fallback Python snippet in §4: should it
  match `tools/vision_prep.py` line-for-line, or be a deliberately
  minimal version that omits the unsharp-mask polish?
- Whether `tools/crop.py` is copied verbatim from `skills/image-cut/`
  or trimmed to remove options ChatGPT will never use.
- Whether to add a tiny smoke test (`tests/test_chatgpt_vision_prep.py`)
  that verifies the 768 px output, mirroring the test style in
  `skills/image-cut/tests/`.
