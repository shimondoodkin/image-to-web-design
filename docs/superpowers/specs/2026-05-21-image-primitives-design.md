# Splitting `image-to-component` into primitive skills — design

**Date:** 2026-05-21
**Status:** Spec — pending user review before implementation planning.

## Problem

`SKILL.md` in this repo is one 33K, eight-stage workflow that conflates several
distinct concerns: a per-agent image-edit dispatch story, an iterative
"remove things from an image" loop, a region-extraction recipe for cropped
component images, a React component synthesis convention, and a visual-diff
loop. The conflation makes the skill hard to maintain, hard to reuse outside
its narrow use case, and uses more context than necessary when invoked.

The neighbouring `crop-tool` project demonstrates the shape we want: small
focused tools with clear interfaces. We will mirror that shape for the
image-editing kit.

## Decomposition

Three SKILL.md files, with strict downward dependency:

```
image-to-web-design   (top, references the two below + ../crop-tool)
        │
        ▼
image-isolation-technique   (mid, references the one below + ../crop-tool)
        │
        ▼
image-edit-instruction   (atomic primitive — the only novel mechanism)
```

`../crop-tool` is referenced by both upper layers but is not modified by this
work.

### What is dropped from the current SKILL.md

These pieces are removed when extracting the primitives; they are not
re-shelved into one of the new skills:

- **SAM / LaMa / IOPaint references** — the atomic primitive's interface is
  agent-facing and accepts an optional mask as an input; whatever upstream
  tool produced the mask is the caller's business. The skill does not
  prescribe SAM or any other mask-producing tool.
- **Pattern A vs Pattern B fork** — collapses into one recipe in the mid
  skill: a single crop yields both an element track and a background track
  by running `image-edit-instruction` twice with different instructions.
- **LPIPS thresholds, dilation pixel counts, base-unit auto-detect, 9-patch
  detection matrix, gradient-fit heuristic, tile autocorrelation** — these
  were tuning knobs that bloated the skill without delivering proportional
  value. The top skill mentions the high-level decision ("if the background
  looks tileable or gradient-y, emit CSS; otherwise ship the asset") as
  prose, without code or thresholds.
- **The model-selection sidebar** — moved into the atomic primitive's
  dispatch section, kept short.
- **Per-call verifier LLM** — caller-driven self-check by the agent that is
  running the loop; no automatic verifier call inside the primitive.

## Skill 1 — `image-edit-instruction` (atomic primitive)

### Purpose

One call, one AI-driven image edit. The only piece of the kit with a novel
mechanism (per-agent dispatch). Everything else in the kit composes calls to
this primitive.

### Interface

- `image` (path) — source image to edit.
- `instruction` (string, English) — natural-language edit instruction.
  Passed through verbatim to the underlying editor. One operation per call.
- `mask` (path, optional) — single-channel PNG, same dimensions as `image`.
  White (255) = the model may modify; black (0) = preserve. Soft-edge greys
  at the boundary are allowed and aid blending; not required.
- `out` (path) — where the edited image is written. Same dimensions as
  `image`. Never overwrites `image`.

The primitive does **not** loop, retry, verify, rewrite the prompt, alter
dimensions, or write any auxiliary files (no metadata, no log, no manifest).
If the underlying call fails, no output is written and the caller sees the
error.

### Dispatch by agent

The SKILL.md will carry three short blocks; the agent reading the skill
follows the block matching its own identity.

- **Gemini agent.** Call the native Gemini image-edit tool. Pass the source
  image, the instruction verbatim, and the mask (if provided) as a second
  image input. Write to `out`.
- **Codex / OpenAI-tools agent.** Call the native image-edit tool
  (GPT image 2 or equivalent). Same shape.
- **Claude.** No native image-edit tool. Shell out to whichever CLI is
  installed:
  - `codex` (batch mode) — currently strongest for instruction edits on
    photographic / UI content.
  - `gemini` (batch mode) — currently strongest on painted / illustrative
    content; preferred fallback.

When both CLIs are installed on a Claude host, the agent picks per call
based on content type (the SKILL.md gives a one-paragraph guide). Order is
not enforced; if the first pick yields a bad result the agent retries with
the other backend.

The skill includes the exact CLI invocation shape for `codex` and `gemini`
batch modes as fenced code blocks with `${IMAGE}`, `${INSTRUCTION}`,
`${MASK}`, `${OUT}` placeholders. No wrapper script is shipped (per user
preference); the CLI surface lives in the skill text.

### Prompt conventions (documented in the skill, applied by caller)

- **Be locational.** Reference where the target is — corner, coordinates,
  colour, position relative to another element.
- **Forbid invention.** End with *"Do not add new objects or text."* and,
  where relevant, *"Replace only with the surrounding texture."*
- **One element per call.** Multi-element instructions degrade. Removing
  three things is three calls with three intermediate output files.

### Mask conventions

- PNG, same dimensions as input.
- White = editable, black = preserve. Greyscale boundaries are blend hints.
- Caller is responsible for producing the mask. Common producers: drawing
  it by hand, deriving it from a bbox via PIL, or any segmentation tool
  the caller has access to. The primitive does not care.

### File conventions (cooperative, not enforced)

- Numbered output files; never overwrite the input. Iterative use produces
  a clean sniff-testable history: `00_original.png`, `01_no_title.png`,
  `02_no_button.png`, ...
- Working directory chosen by the caller. The primitive does not own one.

### Failure modes (documented; caller recognises by eye)

- Output identical to input → model refused or didn't understand. Retry
  with a more locational instruction, or swap backend.
- Output has new artifacts in preserve area → add explicit "do not modify
  unmasked area" clause; consider supplying a mask.
- Output deleted the wrong thing → tighten the locational phrasing.
- Output looks plausible but invented new objects in the fill area → add
  "replace only with surrounding texture" and/or fall back to the other
  backend.
- Output dimensions changed → reject and re-call.

No retry counter, automatic fallback, or internal logic. The calling agent
applies these rules with its own eyes.

## Skill 2 — `image-isolation-technique` (mid)

### Purpose

Teach the agent how to use `image-edit-instruction` (plus `../crop-tool` and
`rembg`) to extract what it wants from a cropped region of an image. The
skill is prose recipes, not code; it references the primitive below and
crop-tool sideways.

### Sections

**a. Crop strategy.** When the parent background is non-uniform (painted
hero, photographic, gradient), do *not* crop tight to the target component.
A loose crop with surrounding context is required because both downstream
recipes (element track, background track) need the surrounding pixels to
reason about texture continuity. When the parent background is solid or
flat, tight cropping is fine. The skill gives one rule and a one-paragraph
explanation; the actual cropping uses `../crop-tool`.

**b. Iterative isolation loop.** The agent calls `image-edit-instruction`
repeatedly with one removal per call, looking at the result between calls
and deciding whether to continue, retry the step with a different
instruction, or stop. The skill documents the order-of-removal heuristic
(foreground text first, UI chrome next, subjects later, decorations last,
painted background never removed) and the stop signals (background looks
worse after a removal; removed area shows invented content; an element
turns out to be structural in the painting).

**c. Two-track extraction from one crop.** This is the missing-piece case
the user flagged: a transparent component (button, badge) sits on a
non-uniform parent. The same large crop produces two outputs by running
`image-edit-instruction` twice with different intents:

- **Element track.** Instruction template:
  *"Keep only the {component} in the {position}. Replace everything else
  with solid white #FFFFFF. Do not modify the {component} itself."*
  Then `rembg i in.png out.png` for clean alpha. Final asset is a transparent
  PNG of the component, plus position metadata recorded by the caller.

- **Background track.** Instruction template:
  *"Remove the {component} in the {position}. Replace with a continuation
  of the surrounding painted texture only. Do not add new objects."*
  Final asset is a clean continuous background patch the caller can sample,
  tile into the parent, or use as the section background.

The two tracks are independent and can run in parallel.

**d. Outpaint recipe.** Extending a canvas is not a separate primitive — it
is `image-edit-instruction` applied to a pre-padded image with a mask of the
new padding region. The skill includes a short PIL snippet that pads an
image to a target size and produces a white-over-padding mask, then a
sample instruction: *"Fill the white masked area with a natural continuation
of the painting around it. Do not modify the unmasked area."*

### Out of scope (deliberately)

- No instruction generation by the skill itself — agents write instructions
  using the templates above and their own judgement.
- No mask production tooling — the mid skill accepts that masks come from
  somewhere (hand-drawn, derived from bbox, segmenter the caller chose).
  It documents the masking *use case* (outpaint) but not how to make a mask
  for arbitrary segmentation.

## Skill 3 — `image-to-web-design` (top)

### Purpose

End-to-end: take a design image, produce a React webpage, render it,
visually compare to the source, iterate until acceptable. Uses
`image-isolation-technique` for all pixel work and `../crop-tool` for
slicing.

### Sections

**e. Design audit / element inventory.** Ask a vision LLM to produce a
structured inventory of every element in the source: section bboxes,
container padding, content max-width, element kind (text / button / badge
/ subject / decoration), bbox, label/content, approximate sizes and
colours, sibling gaps, layout kind (flex column / flex row / grid /
overlay). Stored as `audit.json` in the working directory. The skill
gives the JSON shape and a single example; no auto-detection of the base
spacing unit — the audit captures gaps as measured and the synthesis
section rounds to a small spacing scale by inspection.

**f. Region work.** For each section in the audit, use `../crop-tool` to
slice the section out of the source, then use `image-isolation-technique`
to extract assets from it. The top skill describes the orchestration
("which sections, in what order, with what naming") but defers all the
how-to-isolate detail to the mid skill.

**g. React synthesis.** Tailwind + TypeScript default. Layout primitive
comes from `layout_kind` in the audit (flex column with `gap-N`, flex row,
grid). Absolute positioning is reserved for decorative overlays
(corner badges, callouts). Padding lives on the container; gap lives on
the flex/grid parent. Background is a CSS layer
(`bg-[url(...)]` or styled `<div>`), not an `<img>`. Text is text — never
baked into an image asset.

**h. Render and visually compare.** Render the React output via Playwright
headless at the same resolution as the source. Compare two ways: a
numeric similarity check (LPIPS, optional — the skill mentions it but
does not enforce a threshold) and a vision-LLM semantic diff that asks
"what differs, in design terms, ordered by visual impact." The agent
applies the diff feedback by hand, re-renders, re-diffs. Two or three
rounds is normal.

**i. When to stop.** Stop when the semantic diff returns no items above
the "noticeable" bar, or when remaining diffs are inherent to rendering
(font subpixel differences) and not fixable. Also stop if attempts to
decompose a unified painting damage the painting — use it whole as a
`background-image: cover` asset and layer text/buttons on top. The skill
documents the stop signals; the agent calls it.

### Out of scope (deliberately, vs the current SKILL.md)

- Tile / gradient / 9-patch / unified background classification matrix —
  replaced by one paragraph: "if the background looks tileable or
  gradient-y, emit CSS; otherwise ship the asset; if it's a unified
  painting, do not try to decompose it." No detection code.
- `srcset` vs `<picture>` flowchart — kept as one paragraph: "resolution
  variants → `srcset`; art-directed swap → `<picture>`; everything in
  between → CSS."
- Per-breakpoint pipeline re-run — kept as a sentence: "if the design has
  art-directed mobile, run the audit + region work on the mobile source
  separately."
- File layout diagram — kept; useful and small.

## File and folder layout

This refactor changes the repo from one big `SKILL.md` to:

```
image-to-components/
  skills/
    image-edit-instruction/
      SKILL.md
    image-isolation-technique/
      SKILL.md
    image-to-web-design/
      SKILL.md
  docs/
    superpowers/specs/
      2026-05-21-image-primitives-design.md   ← this file
  SKILL.md                                     ← deleted in implementation
```

The original `SKILL.md` is deleted after the three new skills are in place
and verified.

## Implementation order

When this spec is turned into a plan, the order should be:

1. Write `image-edit-instruction/SKILL.md`. It is self-contained and the
   other two depend on it. Verify by running a single edit call through
   each agent path (Gemini native, Codex native, Claude via `codex`,
   Claude via `gemini`).
2. Write `image-isolation-technique/SKILL.md`. References #1 and
   ../crop-tool. Verify by running each of the four recipes (loose-crop
   element extract, loose-crop background extract, outpaint, iterative
   removal loop) on a sample image end-to-end.
3. Write `image-to-web-design/SKILL.md`. References #2 and ../crop-tool.
   Verify by running the full audit → region work → synthesis → render
   → diff loop on the existing painted-hero example from the current
   SKILL.md's quick-start.
4. Delete the original monolithic `SKILL.md`.

Each step is a separate review/commit gate.
