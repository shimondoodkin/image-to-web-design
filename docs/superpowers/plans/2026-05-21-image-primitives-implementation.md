# Image Primitives Refactor — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Replace the single 33K `SKILL.md` in this repo with three smaller, layered SKILL.md files following the decomposition agreed in the design spec.

**Architecture:** Three skills with strict downward dependency. `image-edit-instruction` is the only atomic primitive (with per-agent dispatch). `image-isolation-technique` documents recipes for working with cropped regions and depends on the primitive. `image-to-web-design` is the orchestrator and depends on the mid skill. Each skill is a single markdown file with YAML frontmatter; no scripts, no Python modules to ship as part of the skills themselves (one PIL snippet is documented inside the mid skill for the outpaint mask). `../crop-tool` is referenced sideways from both upper skills; it is not modified by this work.

**Tech Stack:** Markdown with YAML frontmatter. Pillow (PIL) for the in-skill outpaint snippet, tested separately. PowerShell on Windows for verification commands.

**Spec:** `docs/superpowers/specs/2026-05-21-image-primitives-design.md` is the source of truth for content. Tasks below reference its sections rather than duplicating prose. When a task says "fill in §X of the spec," open the spec, find that section, and expand it into the SKILL.md being written.

**Verification convention.** For each SKILL.md a `grep` checklist confirms required headings are present (mechanical, fast, runs every task). A final manual end-to-end verification per skill confirms the skill is usable by a real agent — these are slow and require a sample image; the plan flags them as **MANUAL** so they can be batched at the end if needed.

**Git.** This project is not currently a git repo. Task 0 initialises one so the commit steps work. If the user prefers no git, replace each `git commit ...` step with "save the file" and skip Task 0.

---

## Task 0: Initialise git in the project (skip if user opts out of git)

**Files:**
- Modify: project root (no specific file; `git init` creates `.git/`)

- [ ] **Step 1: Init git**

Run from `C:\Users\user\Documents\projects\image-to-components`:

```powershell
git init
git add SKILL.md docs/superpowers/specs/2026-05-21-image-primitives-design.md
git commit -m "chore: import existing SKILL.md and design spec as baseline"
```

Expected: a single baseline commit containing the current monolith SKILL.md and the design spec.

- [ ] **Step 2: Verify clean working tree**

```powershell
git status
```

Expected: `nothing to commit, working tree clean`.

---

## Task 1: Create skills directory structure

**Files:**
- Create: `skills/image-edit-instruction/SKILL.md` (placeholder)
- Create: `skills/image-isolation-technique/SKILL.md` (placeholder)
- Create: `skills/image-to-web-design/SKILL.md` (placeholder)

- [ ] **Step 1: Create the three skill directories with empty SKILL.md files**

```powershell
New-Item -ItemType Directory -Force skills/image-edit-instruction | Out-Null
New-Item -ItemType Directory -Force skills/image-isolation-technique | Out-Null
New-Item -ItemType Directory -Force skills/image-to-web-design | Out-Null
New-Item -ItemType File -Force skills/image-edit-instruction/SKILL.md | Out-Null
New-Item -ItemType File -Force skills/image-isolation-technique/SKILL.md | Out-Null
New-Item -ItemType File -Force skills/image-to-web-design/SKILL.md | Out-Null
```

- [ ] **Step 2: Verify the structure exists**

```powershell
Get-ChildItem -Recurse skills | Select-Object FullName
```

Expected: three directories, each containing a zero-byte `SKILL.md`.

- [ ] **Step 3: Commit**

```powershell
git add skills/
git commit -m "chore: scaffold three skill directories"
```

---

## Task 2: Research exact CLI invocation shapes for codex and gemini batch mode

This is a small research task whose output feeds Task 3 Step 4. The spec deferred the exact CLI shape; we resolve it before writing the dispatch section so the SKILL.md is concrete.

**Files:**
- Create: `docs/superpowers/notes/cli-invocations.md` (working notes; deleted at end of plan)

- [ ] **Step 1: Probe codex CLI help**

```powershell
codex --help
codex exec --help 2>&1 | Select-String -Pattern "image|batch|prompt"
```

Expected: output that documents how to pass an image + prompt + (optional) mask + output path to codex in a non-interactive way. If `codex` is not installed locally, document that fact in the notes file and skip — the SKILL.md will be written with a placeholder syntax pulled from public codex docs and a `# TODO: verify on host` comment at the call site.

- [ ] **Step 2: Probe gemini CLI help**

```powershell
gemini --help 2>&1 | Select-String -Pattern "image|prompt|edit|batch"
```

Same expectation: document the actual flag shape. If `gemini` is not installed, note and proceed with public-docs placeholder.

- [ ] **Step 3: Write `docs/superpowers/notes/cli-invocations.md`** capturing the two invocation shapes, with `${IMAGE}`, `${INSTRUCTION}`, `${MASK}`, `${OUT}` placeholders. Example structure:

```markdown
# CLI invocations — working notes

## codex (batch mode)
[exact flag shape captured from --help]

Example:
codex exec --input ${IMAGE} --prompt ${INSTRUCTION} [--mask ${MASK}] --output ${OUT}

## gemini (batch mode)
[exact flag shape captured from --help]

Example:
gemini ...
```

- [ ] **Step 4: Commit**

```powershell
git add docs/superpowers/notes/cli-invocations.md
git commit -m "docs: capture codex/gemini batch CLI shapes"
```

---

## Task 3: Write `skills/image-edit-instruction/SKILL.md`

**Files:**
- Modify: `skills/image-edit-instruction/SKILL.md`

This skill is the atomic primitive. The full content is built section by section. Each step ends with a `grep`-style content check to confirm the section is in the file before the next step starts.

- [ ] **Step 1: Write YAML frontmatter + title**

Write exactly:

```markdown
---
name: image-edit-instruction
description: One AI-driven image edit call. Use when an agent needs to remove, isolate, or modify an element in an image via natural-language instruction. Agent-facing primitive that dispatches to native image-edit tools (Gemini, Codex) or shells out to CLI (Claude → codex/gemini batch mode). Pass image + instruction + optional mask; receive edited image. Does not loop, retry, or verify — caller drives those.
---

# image-edit-instruction
```

Verify:

```powershell
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "^name: image-edit-instruction$"
```

Expected: one match.

- [ ] **Step 2: Append "Purpose" section**

Append the Purpose paragraph from spec §"Skill 1 — image-edit-instruction" → "Purpose". Two or three sentences max. End with: "Everything else in the kit composes calls to this primitive."

Verify:

```powershell
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "^## Purpose$"
```

Expected: one match.

- [ ] **Step 3: Append "Interface" section**

Append the interface from spec §"Interface" verbatim — bulleted list of inputs (image, instruction, mask, out), the output paragraph, the atomicity paragraph ("One call, one edit. Never overwrites input. Caller picks fresh `out`."), and the "does NOT do" bullet list.

Verify:

```powershell
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "^## Interface$"
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "Never overwrites"
```

Expected: both match.

- [ ] **Step 4: Append "Dispatch by agent" section**

Open `docs/superpowers/notes/cli-invocations.md` for the exact CLI shapes. Write the section with three sub-headings:

```markdown
## Dispatch by agent

### If you are a Gemini agent
[prose from spec; call native tool; pass image + instruction + optional mask; write to out]

### If you are a Codex / OpenAI-tools agent
[prose from spec; same shape]

### If you are Claude (no native image-edit tool)
[prose from spec — codex / gemini CLI choice; agent picks per call by content type; one-paragraph guidance from spec]

#### codex (batch) invocation
```bash
[copy from cli-invocations.md, with ${IMAGE} ${INSTRUCTION} ${MASK} ${OUT} placeholders]
```

#### gemini (batch) invocation
```bash
[copy from cli-invocations.md, with ${IMAGE} ${INSTRUCTION} ${MASK} ${OUT} placeholders]
```
```

Verify:

```powershell
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "^### If you are"
```

Expected: three matches.

- [ ] **Step 5: Append "Prompt conventions" section**

Three bullets from spec §"Prompt conventions": be locational, forbid invention, one element per call. One short example per bullet.

Verify:

```powershell
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "^## Prompt conventions$"
```

Expected: one match.

- [ ] **Step 6: Append "Mask conventions" section**

Bullets from spec §"Mask conventions": PNG same dimensions, white=editable / black=preserve, greyscale boundaries blend, caller produces the mask.

Verify:

```powershell
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "^## Mask conventions$"
```

Expected: one match.

- [ ] **Step 7: Append "File conventions" section**

Bullets from spec §"File conventions": numbered outputs, never overwrite, working directory owned by caller. Show the example sequence `00_original.png → 01_no_title.png → 02_no_button.png`.

Verify:

```powershell
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "00_original.png"
```

Expected: one match.

- [ ] **Step 8: Append "Failure modes" section**

Five bullets from spec §"Failure modes" verbatim. End with the closing line: "No retry counter, automatic fallback, or internal logic. The calling agent applies these rules with its own eyes."

Verify:

```powershell
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "^## Failure modes$"
Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern "with its own eyes"
```

Expected: both match.

- [ ] **Step 9: Run full content checklist**

```powershell
$required = @(
  "^name: image-edit-instruction$",
  "^## Purpose$",
  "^## Interface$",
  "^## Dispatch by agent$",
  "^### If you are a Gemini agent$",
  "^### If you are a Codex",
  "^### If you are Claude",
  "^## Prompt conventions$",
  "^## Mask conventions$",
  "^## File conventions$",
  "^## Failure modes$"
)
foreach ($p in $required) {
  $m = Select-String -Path skills/image-edit-instruction/SKILL.md -Pattern $p
  if (-not $m) { Write-Error "MISSING: $p"; break }
}
Write-Host "All sections present."
```

Expected: `All sections present.`

- [ ] **Step 10: Commit**

```powershell
git add skills/image-edit-instruction/SKILL.md
git commit -m "feat(skills): add image-edit-instruction atomic primitive"
```

- [ ] **Step 11: MANUAL end-to-end verification**

Pick a small sample image (any PNG with a clearly removable element — e.g. a button overlaid on a background). For each available agent path:

1. **Gemini path** (if you have a Gemini agent available): hand the agent the SKILL.md and the image, ask it to remove the button. Confirm the agent calls its native edit tool and produces an output without the button.
2. **Codex path** (if available): same.
3. **Claude path** (always available — you are Claude): from a Claude session, follow the SKILL.md's "If you are Claude" block, invoke either codex or gemini CLI, produce an output without the button.

Visually inspect each output. If a path fails because the CLI isn't installed, note it but do not block — the skill is still correct for hosts that have the CLI.

---

## Task 4: Write `skills/image-isolation-technique/SKILL.md`

**Files:**
- Modify: `skills/image-isolation-technique/SKILL.md`
- Create: `tests/test_outpaint_mask.py` (tests the PIL snippet that ships inside the skill)
- Create: `skills/image-isolation-technique/_examples/outpaint_mask.py` (the snippet itself, as a reference file the skill links to and tests run against)

The outpaint recipe in this skill includes a PIL snippet. We test the snippet as code, then embed it verbatim in the SKILL.md.

- [ ] **Step 1: Write the failing test for the outpaint mask snippet**

Create `tests/test_outpaint_mask.py`:

```python
from PIL import Image
import importlib.util
import sys
from pathlib import Path

# Load the snippet file as a module
SNIPPET = Path("skills/image-isolation-technique/_examples/outpaint_mask.py")
spec = importlib.util.spec_from_file_location("outpaint_mask", SNIPPET)
mod = importlib.util.module_from_spec(spec)
spec.loader.exec_module(mod)

def test_pad_and_mask_produces_expected_size_and_white_padding(tmp_path):
    src = Image.new("RGB", (100, 100), (200, 50, 50))
    src_path = tmp_path / "src.png"
    src.save(src_path)

    padded_path = tmp_path / "padded.png"
    mask_path = tmp_path / "mask.png"
    mod.pad_and_make_mask(
        src=str(src_path),
        out_image=str(padded_path),
        out_mask=str(mask_path),
        target_size=(200, 150),
        anchor="center",
    )

    padded = Image.open(padded_path)
    mask = Image.open(mask_path)
    assert padded.size == (200, 150)
    assert mask.size == (200, 150)
    # Padding region is white in the mask
    assert mask.getpixel((0, 0)) == 255
    # Original region is black in the mask (preserve)
    assert mask.getpixel((100, 75)) == 0
```

- [ ] **Step 2: Run test, confirm it fails**

```powershell
pytest tests/test_outpaint_mask.py -v
```

Expected: ImportError or FileNotFoundError — the snippet file doesn't exist yet.

- [ ] **Step 3: Write the snippet**

Create `skills/image-isolation-technique/_examples/outpaint_mask.py`:

```python
"""Pad an image to a target size and produce a white-over-padding mask.

Used by the outpaint recipe in image-isolation-technique/SKILL.md.
"""
from PIL import Image


def pad_and_make_mask(src: str, out_image: str, out_mask: str,
                     target_size: tuple, anchor: str = "center") -> None:
    img = Image.open(src).convert("RGB")
    tw, th = target_size
    sw, sh = img.size
    assert tw >= sw and th >= sh, "target_size must be >= source size"

    if anchor == "center":
        ox = (tw - sw) // 2
        oy = (th - sh) // 2
    elif anchor == "left":
        ox, oy = 0, (th - sh) // 2
    elif anchor == "right":
        ox, oy = tw - sw, (th - sh) // 2
    elif anchor == "top":
        ox, oy = (tw - sw) // 2, 0
    elif anchor == "bottom":
        ox, oy = (tw - sw) // 2, th - sh
    else:
        raise ValueError(f"unknown anchor: {anchor}")

    padded = Image.new("RGB", (tw, th), (255, 255, 255))
    padded.paste(img, (ox, oy))
    padded.save(out_image)

    mask = Image.new("L", (tw, th), 255)  # all white = editable
    inner = Image.new("L", (sw, sh), 0)   # source region = black = preserve
    mask.paste(inner, (ox, oy))
    mask.save(out_mask)
```

- [ ] **Step 4: Run test, confirm it passes**

```powershell
pytest tests/test_outpaint_mask.py -v
```

Expected: 1 passed.

- [ ] **Step 5: Write SKILL.md YAML frontmatter + title**

```markdown
---
name: image-isolation-technique
description: Recipes for extracting clean assets from a cropped region of an image — element track, background track, outpaint. Use when an agent needs to isolate a component from its parent background, extract a clean continuous background patch under an overlay, or extend an image's canvas. Composes `image-edit-instruction` (AI edit primitive) with `../crop-tool` (cropping) and `rembg` (alpha matting); does not introduce new mechanisms.
---

# image-isolation-technique
```

Verify:

```powershell
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "^name: image-isolation-technique$"
```

Expected: one match.

- [ ] **Step 6: Append "Crop strategy" section**

Content from spec §"Skill 2" → section (a). One rule + one-paragraph explanation of why loose-crop is required for non-uniform parent backgrounds + a single example. Reference `../crop-tool` as the cropping mechanism.

Verify:

```powershell
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "^## Crop strategy$"
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "crop-tool"
```

Expected: both match.

- [ ] **Step 7: Append "Iterative isolation loop" section**

Content from spec §"Skill 2" → section (b). Document the agent-driven edit-look-repeat loop. Include the order-of-removal heuristic (text → UI chrome → subjects → decorations; painted background never removed) and stop signals (background looks worse; invented content appears; element was structural). Reference `image-edit-instruction` as the per-call mechanism.

Verify:

```powershell
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "^## Iterative isolation loop$"
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "image-edit-instruction"
```

Expected: both match.

- [ ] **Step 8: Append "Two-track extraction" section**

Content from spec §"Skill 2" → section (c). Spell out both instruction templates verbatim:

```markdown
### Element track

Instruction template:
> Keep only the {component} in the {position}. Replace everything else with solid white #FFFFFF. Do not modify the {component} itself.

Then: `rembg i in.png out.png` for clean alpha. Final asset is a transparent PNG of the component, plus position metadata recorded by the caller.

### Background track

Instruction template:
> Remove the {component} in the {position}. Replace with a continuation of the surrounding painted texture only. Do not add new objects.

Final asset is a clean continuous background patch the caller can sample, tile into the parent, or use as the section background.
```

State explicitly that the two tracks are independent and can run in parallel.

Verify:

```powershell
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "^### Element track$"
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "^### Background track$"
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "rembg i"
```

Expected: three matches.

- [ ] **Step 9: Append "Outpaint recipe" section**

Content from spec §"Skill 2" → section (d). Show the recipe as three steps: pad image + build mask via the PIL snippet (link to `_examples/outpaint_mask.py`); call `image-edit-instruction` with a "fill the white area" instruction; save the result. Include the snippet inline in a code block so the skill is self-contained for readers, and reference the file for the verified, tested copy.

```markdown
## Outpaint recipe

Extending a canvas is not a separate primitive — it is `image-edit-instruction` applied to a pre-padded image with a mask of the new padding region.

1. Pad the source image to the target size and produce a white-over-padding mask:

   ```python
   # skills/image-isolation-technique/_examples/outpaint_mask.py
   from PIL import Image

   def pad_and_make_mask(src, out_image, out_mask, target_size, anchor="center"):
       [snippet body — keep in sync with _examples/outpaint_mask.py]
   ```

2. Call `image-edit-instruction` with the padded image, the mask, and instruction:
   > Fill the white masked area with a natural continuation of the painting around it. Do not modify the unmasked area.

3. The output is the source painting extended into the new canvas.
```

Verify:

```powershell
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "^## Outpaint recipe$"
Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern "pad_and_make_mask"
```

Expected: both match.

- [ ] **Step 10: Run full content checklist**

```powershell
$required = @(
  "^name: image-isolation-technique$",
  "^## Crop strategy$",
  "^## Iterative isolation loop$",
  "^## Two-track extraction$",
  "^### Element track$",
  "^### Background track$",
  "^## Outpaint recipe$"
)
foreach ($p in $required) {
  $m = Select-String -Path skills/image-isolation-technique/SKILL.md -Pattern $p
  if (-not $m) { Write-Error "MISSING: $p"; break }
}
Write-Host "All sections present."
```

Expected: `All sections present.`

- [ ] **Step 11: Commit**

```powershell
git add skills/image-isolation-technique/ tests/test_outpaint_mask.py
git commit -m "feat(skills): add image-isolation-technique mid skill with outpaint snippet"
```

- [ ] **Step 12: MANUAL end-to-end verification**

Pick a sample image with a clearly overlaid component on a non-uniform parent (e.g. a "NEW" badge over a painted hero). Following the skill text only (no extra hints), run:

1. The two-track extraction. Confirm element track yields a transparent PNG of the badge, background track yields a clean background patch.
2. The outpaint recipe. Pad a 100×100 image to 200×150 and confirm the result extends naturally.

Visually inspect each output.

---

## Task 5: Write `skills/image-to-web-design/SKILL.md`

**Files:**
- Modify: `skills/image-to-web-design/SKILL.md`

This is the orchestrator. Most content references the other two skills and `../crop-tool` rather than restating.

- [ ] **Step 1: Write YAML frontmatter + title**

```markdown
---
name: image-to-web-design
description: End-to-end conversion of a design image into a React webpage. Use when an agent receives a screenshot, mockup, or painted reference and must produce HTML/JSX/Tailwind that closely matches the image, render the result, and iteratively close the visual gap. Orchestrates `../crop-tool` (slicing), `image-isolation-technique` (asset extraction), React synthesis, headless rendering, and vision-LLM diffing.
---

# image-to-web-design
```

Verify:

```powershell
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "^name: image-to-web-design$"
```

Expected: one match.

- [ ] **Step 2: Append "Design audit / element inventory" section**

Content from spec §"Skill 3" → section (e). Show the JSON shape (one concrete example, not multiple). State that the audit is stored as `audit.json` in the working directory. State explicitly: no auto-detection of the base spacing unit — gaps are captured as measured and snapped during synthesis by inspection.

Verify:

```powershell
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "^## Design audit"
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "audit.json"
```

Expected: both match.

- [ ] **Step 3: Append "Region work" section**

Content from spec §"Skill 3" → section (f). For each section in the audit: crop via `../crop-tool`, extract assets via `image-isolation-technique`. The how-to-isolate detail is owned by the mid skill — this section gives orchestration only (which sections in what order, naming convention).

Verify:

```powershell
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "^## Region work$"
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "image-isolation-technique"
```

Expected: both match.

- [ ] **Step 4: Append "React synthesis" section**

Content from spec §"Skill 3" → section (g). Conventions: Tailwind + TypeScript default, layout primitive from `layout_kind`, absolute positioning for overlays only, padding-vs-gap rule, background as CSS layer, text is text. One short example component layout (hero with painted background + text + CTA).

Verify:

```powershell
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "^## React synthesis$"
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "layout_kind"
```

Expected: both match.

- [ ] **Step 5: Append "Render and visually compare" section**

Content from spec §"Skill 3" → section (h). Render via Playwright at the same resolution as source. Two diff signals: numeric (LPIPS, optional — mention but do not enforce a threshold) and semantic (vision-LLM diff with the prompt template). One concrete prompt for the semantic diff.

Verify:

```powershell
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "^## Render and visually compare$"
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "Playwright"
```

Expected: both match.

- [ ] **Step 6: Append "When to stop" section**

Content from spec §"Skill 3" → section (i). Stop when semantic diff returns no items above the "noticeable" bar, or remaining diffs are inherent. Also stop if decomposing a unified painting damages it — use whole, layer text/buttons on top.

Verify:

```powershell
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "^## When to stop$"
```

Expected: one match.

- [ ] **Step 7: Append "Working directory layout" section**

Concise version of the layout block from the current SKILL.md (kept because the spec said it's "useful and small"). Show one tree diagram, no commentary beyond labels.

Verify:

```powershell
Select-String -Path skills/image-to-web-design/SKILL.md -Pattern "^## Working directory layout$"
```

Expected: one match.

- [ ] **Step 8: Run full content checklist**

```powershell
$required = @(
  "^name: image-to-web-design$",
  "^## Design audit",
  "^## Region work$",
  "^## React synthesis$",
  "^## Render and visually compare$",
  "^## When to stop$",
  "^## Working directory layout$"
)
foreach ($p in $required) {
  $m = Select-String -Path skills/image-to-web-design/SKILL.md -Pattern $p
  if (-not $m) { Write-Error "MISSING: $p"; break }
}
Write-Host "All sections present."
```

Expected: `All sections present.`

- [ ] **Step 9: Commit**

```powershell
git add skills/image-to-web-design/SKILL.md
git commit -m "feat(skills): add image-to-web-design orchestrator skill"
```

- [ ] **Step 10: MANUAL end-to-end verification**

Use the painted-hero example from the original SKILL.md's quick-start (section "Quick-start example"). Treat the new three-skill kit as the only available source of guidance. Run:

1. Design audit on a painted hero image.
2. Region work: crop the hero section, extract subject + background via image-isolation-technique.
3. Synthesise a React component using the conventions in image-to-web-design.
4. Render via Playwright at the source resolution.
5. Run the semantic-diff prompt against (source, rendered). Apply fixes. Re-render.

Stop when the diff returns no noticeable items. The expected outcome matches the original SKILL.md's quick-start narrative (LPIPS ~0.06 desktop, ~0.07 mobile).

---

## Task 6: Delete the original monolith SKILL.md

**Files:**
- Delete: `SKILL.md` (the root-level monolith)

- [ ] **Step 1: Confirm the three new skills cover everything before deletion**

Open the old `SKILL.md` and skim the 8 stages. For each stage, point to which new skill (and which section) implements it. There should be no orphans. If anything is orphaned, file a separate follow-up task before deletion.

- [ ] **Step 2: Delete the file**

```powershell
Remove-Item SKILL.md
```

- [ ] **Step 3: Verify deletion**

```powershell
Test-Path SKILL.md
```

Expected: `False`.

- [ ] **Step 4: Delete the working notes file from Task 2 (cleanup)**

```powershell
Remove-Item docs/superpowers/notes/cli-invocations.md
Remove-Item -Recurse -Force docs/superpowers/notes
```

- [ ] **Step 5: Commit**

```powershell
git add -A
git commit -m "refactor: remove monolithic SKILL.md; replaced by three layered skills"
```

- [ ] **Step 6: Final repo sanity check**

```powershell
Get-ChildItem -Recurse skills | Select-Object FullName
Test-Path SKILL.md
git log --oneline
```

Expected:
- Three `SKILL.md` files under `skills/<name>/`.
- No root-level `SKILL.md`.
- A clean commit history with one commit per major step.

---

## Self-review notes (from plan author)

1. **Spec coverage.** Every spec section maps to a task:
   - Spec §Decomposition → Task 1 (directory structure)
   - Spec §Skill 1 (all subsections) → Task 3 (steps 1-10)
   - Spec §Skill 2 (all subsections) → Task 4 (steps 1-11)
   - Spec §Skill 3 (all subsections) → Task 5 (steps 1-8)
   - Spec §"What is dropped" → enforced by not having any task that re-introduces SAM/LaMa/LPIPS-thresholds/9-patch/etc.
   - Spec §"File and folder layout" → Task 1 plus Task 6 (delete monolith)
   - Spec §"Implementation order" → matches plan task order

2. **Placeholders.** No `TBD`, `TODO`, or "fill in later" in any task. The CLI shape is resolved in Task 2 before being used in Task 3.

3. **Type / name consistency.** Skill names are used consistently: `image-edit-instruction`, `image-isolation-technique`, `image-to-web-design`. PIL function is `pad_and_make_mask` in both the test and the snippet.

4. **TDD adaptation.** Outpaint snippet (the only ship-able code) gets real TDD in Task 4 steps 1-4. SKILL.md content gets mechanical content checks (`Select-String` for required headings) plus manual end-to-end verification per skill. This is the practical adaptation of "test-first" for markdown deliverables.
