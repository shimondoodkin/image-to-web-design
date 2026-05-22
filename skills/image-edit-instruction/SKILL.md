---
name: image-edit-instruction
description: One AI-driven image edit call. Use when an agent needs to remove, isolate, or modify an element in an image via a natural-language instruction. Agent-facing primitive that dispatches to native image-edit tools (Gemini, Codex) or shells out to a CLI sub-agent (Claude → codex/gemini in headless mode). Pass image + instruction + optional mask; receive edited image. Does not loop, retry, or verify — caller drives those.
---

# image-edit-instruction

> **Part of the [image-to-web-design](https://github.com/shimondoodkin/image-to-web-design) kit.**
> Sibling skills that compose with this one: `image-isolation-technique`,
> `image-cut`, `image-to-web-design`. If you found this file on its own,
> the full kit gives you the recipes and tooling that use this primitive —
> install with `npx skills add shimondoodkin/image-to-web-design`.

## Purpose

One call, one AI-driven image edit. The only piece of the image-editing kit with a novel mechanism: agent-specific dispatch. Everything else (iterative isolation, two-track extraction, outpaint, the webpage builder) composes calls to this primitive.

The contract is intentionally minimal so the primitive stays small and so failure modes are explicit. The calling agent is expected to look at the result with its own eyes and decide whether to continue, retry, or stop.

## Interface

Inputs:

- `image` (path): the source image to edit. Must exist and be readable. Never mutated.
- `instruction` (string, English): a natural-language edit instruction. Passed through to the underlying editor verbatim. One operation per call (see Prompt conventions).
- `mask` (path, optional): a PNG, same dimensions as `image`, single channel or RGB-with-equal-channels. White (255) = the model may modify; black (0) = preserve. Greyscale boundaries are allowed and act as blend hints.
- `out` (path): where the edited image is written. Same dimensions as `image`. Must not equal `image`.

Output:

- A single image file at `out`, written atomically by the underlying editor. No metadata file, no log, no manifest.

Atomicity guarantees:

- One call = one edit. The primitive never loops on its own.
- The primitive never overwrites `image`. The caller picks a fresh `out` per step.
- If the underlying call fails, no `out` is written and the caller sees the error.

The primitive does **not** do:

- No verification — the caller looks at `out`.
- No retry — the caller decides whether to call again with a different instruction.
- No prompt rewriting or safety-wrapping — `instruction` is passed through verbatim.
- No background removal, no outpainting, no cropping — those are recipes that *compose* this primitive, not features of it.
- No dimension change — if the underlying tool returns a differently-sized image, the caller should reject and re-call.

## Dispatch by agent

The three blocks below correspond to the three agent identities this primitive is designed for. Follow the block that matches your own.

### If you are a Gemini agent

Call your native image-generation/edit tool. Pass the source image, the instruction verbatim, and the mask (if provided) as a second image input. Save the result to `out`. Do not iterate inside the tool call — that's the caller's job, not the editor's.

### If you are a Codex / OpenAI-tools agent

Call the native image-edit tool (GPT image 2 or equivalent). Pass the source image, the instruction verbatim, and the mask (if provided). Save the result to `out`. Same shape as Gemini above.

### If you are Claude (no native image-edit tool)

Shell out to a CLI sub-agent. Both `codex` and `gemini` work for this; on a host where both are installed the agent picks per call based on content type:

- **codex** tends to win on photographic, UI, and dense-text content. Most accurate for instruction edits on those.
- **gemini** tends to win on painted / illustrative / non-realistic content. Better at preserving artistic style.

There is no enforced default order. Try the one most likely for the content; if the result is off, retry with the other backend.

#### codex (headless) invocation

```bash
codex exec \
    -i "${IMAGE}" \
    --sandbox workspace-write \
    --skip-git-repo-check \
    "${INSTRUCTION}. Save the edited image to ${OUT}."
```

With a mask:

```bash
codex exec \
    -i "${IMAGE}" -i "${MASK}" \
    --sandbox workspace-write \
    --skip-git-repo-check \
    "${INSTRUCTION}. The second attached image is a mask: white=editable, black=preserve. Save the edited image to ${OUT}."
```

#### gemini (headless) invocation

Gemini doesn't expose an `--image` flag; reference the file inside the prompt with `@path` syntax. Use `--include-directories` to bring the file's folder into the workspace.

```bash
gemini \
    --yolo \
    --include-directories "$(dirname "${IMAGE}")" \
    -p "Edit the image at @${IMAGE}. ${INSTRUCTION}. Save the edited image to ${OUT}."
```

With a mask:

```bash
gemini \
    --yolo \
    --include-directories "$(dirname "${IMAGE}")" \
    -p "Edit the image at @${IMAGE} using the mask at @${MASK} (white=editable, black=preserve). ${INSTRUCTION}. Save the edited image to ${OUT}."
```

Both shapes assume the sub-agent inside the CLI is allowed to call its image-edit tool. On a freshly-installed codex/gemini this is usually the case; on locked-down configs the user must enable the relevant tool first.

## Prompt conventions

Three rules. Apply them when writing `instruction`.

- **Be locational.** Mention where the target is — corner, coordinates, colour, position relative to another element. Locality is what keeps the editor focused.
  - Good: *"Remove the red badge in the top-right corner around (1700, 90)."*
  - Bad: *"Remove the badge."*
- **Forbid invention.** End with *"Do not add new objects or text."* and, where relevant, *"Replace only with the surrounding texture."* Editors will happily hallucinate plausible content into a removed area; the only defence is asking them not to.
- **One element per call.** Multi-element instructions degrade fast. Removing three things is three calls with three intermediate output files — not one big prompt.

## Mask conventions

- PNG, same dimensions as input.
- Single channel (`L` mode) or RGB-with-equal-channels.
- White (255) = the model may modify.
- Black (0) = preserve.
- Greyscale (1–254) at the boundary acts as a blend hint and helps avoid hard seams.
- The caller is responsible for producing the mask. Common producers: drawing it by hand in an image editor, deriving it from a bounding box with a few lines of PIL, or asking a segmentation tool the caller has access to. The primitive does not prescribe a producer.

## File conventions

Cooperative, not enforced — but agents that follow these conventions produce sniff-testable working directories that humans and other agents can review without reading any code.

- **Numbered outputs, never overwrite.** Iterative use produces a clean history: `00_original.png` → `01_no_title.png` → `02_no_button.png` → `03_no_badge.png`.
- **Working directory is the caller's choice.** The primitive does not own one.
- **Masks live alongside in a `masks/` subdirectory**, named after what they cover: `masks/badge.png`, `masks/title.png`.

## Failure modes

The calling agent sees these symptoms with its own eyes. There is no automatic verification.

- **Output is identical to input.** The model refused or didn't understand. Retry with a more locational instruction, or swap backend.
- **Output has new artifacts in the supposed-to-preserve area.** Add an explicit *"do not modify the unmasked area"* clause; consider supplying a mask if one wasn't provided.
- **Output deletes the wrong thing, or part of the wrong thing.** Tighten the locational phrasing (coordinates, colour, relative position).
- **Output looks plausible but the fill area contains invented objects.** Add *"replace only with the surrounding texture"* and/or fall back to the other backend.
- **Output dimensions changed.** Reject and re-call. The primitive promises same-dimensions output; if the editor breaks this, treat the result as garbage.

No retry counter, automatic fallback, or internal logic. The calling agent applies these rules with its own eyes.
