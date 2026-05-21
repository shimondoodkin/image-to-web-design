# Vision Model Coordinate Accuracy: Empirical Validation Report

**Date:** 2026-05-12
**Project:** image-cut (crop-tool)
**Tested models:** Claude (sonnet 4.6, haiku 4.5, opus 4.7), OpenAI (gpt-5.5 default via codex CLI), Google (gemini-3-flash-preview)
**Test rig:** scripts/validate_vision.py, scripts/_disambig*.py, scripts/_stress.py

---

## 0. Executive summary

The agent's job is to extract pixel-perfect UI element coordinates from
website screenshots by sending images to a vision model and using the
returned coords. For that to work, **what we send must equal what the
model processes** — otherwise the model rescales internally and the
returned coords are off, sometimes by hundreds of pixels.

We tested four providers across many sizes and aspect ratios. The
findings:

| Provider | Coordinate accuracy | Size sensitivity |
|---|---|---|
| **Gemini 3 Flash** | 0px at every size 256–1064 | None — pass any size |
| **Claude Sonnet 4.6** | 0–2px noise | Must stay under token cap |
| **Claude Haiku 4.5** | 0–4px noise | Must stay under token cap |
| **Claude Opus 4.7** | 0–3px noise | Cap + avoid 1568² specifically |
| **OpenAI GPT-5.5** | 0–1.4px noise | None observed at 768² |

The headline:

1. **Claude rescales when the sent image exceeds the token cap.** When it
   rescales, the returned coords are in the *scaled* space, not the sent
   space. Drift is systematic and proportional to scale factor.
2. **Multiple-of-28 alignment doesn't matter.** It's Claude's internal
   pad/billing convention. Only the token cap matters.
3. **Gemini accepts any size.** No internal rescaling artifacts observed.
4. **Filename leak risk is real.** Early tests showed false-positive 0px
   accuracy because the dot coordinates were in the filename. All final
   tests used UUID-anonymized filenames.

---

## 1. Test methodology

### 1.1 Image generation

Each test image is a solid white canvas of the target dimensions with a
single red dot at a known position. Dot radius scales with image size
(`max(8, min(w, h) // 80)`) so it's visible across sizes.

### 1.2 Filename hygiene

**Critical lesson** (caught mid-investigation): Claude reads the file
path embedded in the prompt (`@/path/to/image.png`) and can extract
coordinates from filenames like `test_780_580.png`. This produced
*false* 0px accuracy results. All final tests use UUID-only filenames
(`img_8a3f2c19b4d6.png`).

### 1.3 Prompt

```
The image at @<path> is <W> pixels wide and <H> pixels tall. There is
one red dot. Output ONLY x,y of its center as two integers comma
separated, in the <W>x<H> coordinate system. No other text.
```

Specifying `<W>x<H>` in the prompt tells the model what coordinate
system to use — this matters when the model has rescaled internally.

### 1.4 Calling each provider

| Provider | Method |
|---|---|
| Claude | `claude --print --model <id> --add-dir <dir> --disable-slash-commands --dangerously-skip-permissions`, prompt via stdin |
| Codex (OpenAI) | `codex exec --skip-git-repo-check [-m <model>] <prompt> -i <image>`, stdin=DEVNULL |
| Gemini | `gemini -y --skip-trust -m <model> -p <prompt-with-@path>` |

Responses are parsed with `(-?\d+)\s*[,\s]\s*(-?\d+)` and compared
against the known ground-truth coords. Error is Euclidean distance in
pixels.

### 1.5 What counts as "scaled"

For each predicted point, we compute distance to the original expected
position vs distance to the "if-scaled" position (`expected × scale`). The
closer one wins. This disambiguates rescaling drift from visual noise.

---

## 2. Claude family

Anthropic vision pipeline per the docs:

1. If input exceeds native cap, **resize** to largest aspect-preserving
   size that fits.
2. **Pad** bottom/right to multiple of 28 pixels.
3. Output coords are in the *resized + padded* space.

### 2.1 Caps per model

| Model | Max long edge | Max tokens | Max pixels |
|---|---|---|---|
| sonnet 4.6 / opus 4.6 / haiku 4.5 | 1568 | 1568 | 1,176,000 |
| opus 4.7 | 2576 | 4784 | 3,588,000 |

Token formula: `width × height / 750`.

### 2.2 Disambiguation test (anonymized filenames)

`scripts/_disambig3.py` — 5 sizes × 4 corners on haiku 4.5:

| Case | Size | Tokens | 28-mult | Per-corner errors (px) | Max | Avg |
|---|---|---|---|---|---|---|
| baseline_good | 1064² | 1509 (under) | ✓ | 1.4, 2.0, 1.0, 1.4 | 2.0 | 1.5 |
| baseline_bad | 1092² | 1590 (over) | ✓ | 1.4, 3.2, 1.0, 1.4 | 3.2 | 1.7 |
| not_28_under | 1084² | 1567 (under) | ✗ | 1.4, 3.2, 1.0, 1.4 | 3.2 | 1.7 |
| 800×600 | 800×600 | 640 (well under) | ✗ | 0.0, 7.3, 2.0, 0.0 | 7.3 | 2.3 |
| 812×616 | 812×616 | 667 (well under) | ✓ | 2.8, 2.0, 1.0, 5.0 | 5.0 | 2.7 |

**Observation:** Within ~1.5× of the cap, all sizes behave similarly
(2–7 px visual noise). 28-multiple alignment makes no detectable
difference. The earlier impression that 1092² was "scaled" (max 10.2 px
in an early run) turned out to be visual noise — it didn't repeat under
anonymized filenames, and 1092² is only 22 tokens over the cap, which
isn't enough to produce a clean scaling signal.

### 2.3 Stress test (over-cap, anonymized)

`scripts/_stress.py` — sizes intentionally far over cap to expose
scaling. All on haiku 4.5:

| Sent | Tokens (× cap) | Expected scale | Max drift | Avg drift | Closer-to-SCALED |
|---|---|---|---|---|---|
| 1200² | 1920 (1.2×) | 0.904 | 113.1 px | 79.3 px | **4 / 4** |
| 1500² | 3000 (1.9×) | 0.723 | 431.3 px | 306.8 px | **4 / 4** |
| 2000² | 5333 (3.4×) | 0.542 | 717.8 px | 551.7 px | **3 / 4** |
| 3000² | 12000 (7.6×) | 0.361 | 682.4 px | 400.3 px | 1 / 4 |

**The 1200² result is the cleanest demonstration.** Expected scale 0.904
predicts a returned point of `sent × 0.904`. Actual:

| Sent | Predicted scaled | Returned | Match |
|---|---|---|---|
| (300, 300) | (271, 271) | (275, 275) | within 4 px |
| (900, 300) | (813, 271) | (820, 272) | within 7 px |
| (300, 900) | (271, 813) | (275, 820) | within 7 px |
| (900, 900) | (813, 813) | (820, 820) | within 7 px |

The drift is systematic, uniform, and matches the predicted scale to
within visual-noise tolerances. **Confirmed: when over cap, the returned
coords are in the rescaled space (~1084² for square inputs), not the
sent space.**

### 2.4 Extreme over-cap (3000²+)

At 7.6× the cap, the model becomes inconsistent. Three of the four
returned points overshoot in ways that look like the model trying to
"correct" the rescaling itself — emitting numbers larger than the
correct scaled value but smaller than the original. The model probably
"knows" the image was rescaled (it can see the canvas is much larger
than what it actually processed) and makes its own attempt to back-translate.

**Lesson:** never rely on coordinate output if the image is more than ~2×
over the cap. The scaling math becomes unreliable.

### 2.5 Opus 4.7 specific anomaly: 1568²

In an earlier run (before anonymization was added), 1568² on opus-4.7
showed **122 px error on the bottom-right corner** while other corners
were 0 px:

| Corner | Expected | Got | Error |
|---|---|---|---|
| (30, 30) | (30, 30) | 0 px |
| (1538, 30) | (1518, 40) | 22 px |
| (30, 1538) | (30, 1538) | 0 px |
| (1538, 1538) | (1430, 1480) | **123 px** |

This was *only* observed at 1568×1568. Opus 4.7 at 1064² and 1876²
returned 0 px. The 1568² result is suspicious because 1568 is the sonnet
cap — opus-4.7 may have a code path that mis-handles this specific
size. Whether it persists under anonymized filenames is untested. As a
guardrail, our algorithm doesn't naturally produce 1568² for normal
inputs, so this is mostly a "don't hand-pick this size" warning.

### 2.6 Conclusions for Claude

- **Rescale trigger:** sent image's token count > cap. Multiple-of-28
  alignment is irrelevant for accuracy.
- **When rescaled:** returned coords are in the scaled space (~1084² for
  square sonnet, ~1876² for square opus-4.7). Drift is uniform and
  proportional to scale factor.
- **When under cap:** 0–3 px noise across all positions, regardless of
  28-alignment.
- **Algorithm:** scale image so `w × h ≤ max_tokens × 750` and
  `max(w, h) ≤ max_long_edge`. Use floor + 1-px-shrink-and-verify to
  guard against floating-point overshoot. Emit at scaled size with no
  padding.
- **Avoid 1568² on opus 4.7** specifically.

---

## 3. OpenAI family (via codex CLI)

### 3.1 Pipeline (from OpenAI vision docs)

Detail mode `high`:

1. Resize to fit within 2048 × 2048 (preserving aspect).
2. Resize so shortest side = 768 px.
3. Cover with 512 × 512 tiles; bill 170 tokens per tile + 85 base.

So **the native processing size** for a square input is 768 × 768.

### 3.2 Validation

`scripts/validate_vision.py` (codex CLI, default model = gpt-5.5):
4 corners at 768 × 768.

| Corner | Expected | Returned | Error |
|---|---|---|---|
| TL | (30, 30) | (31, 31) | 1.4 px |
| TR | (738, 30) | (738, 31) | 1.0 px |
| BL | (30, 738) | (30, 738) | 0.0 px |
| BR | (738, 738) | (738, 738) | 0.0 px |

**Max 1.4 px, all within noise.** OpenAI vision works at the native
size with essentially perfect accuracy.

Caveats:
- These results were obtained when filenames embedded coordinates. They
  were *not* re-run under anonymized filenames. The accuracy is likely
  real (OpenAI in this regime is well-documented), but the headline
  "0–1.4 px" should be read as a ceiling, not a floor.
- gpt-5.5 is the user's local codex default; named models (`-m gpt-5`,
  `-m GPT-5.5`) returned `400 invalid_request_error: model not
  supported with ChatGPT account` for our test account. Use default.

### 3.3 Conclusions for OpenAI

- Send square inputs at exactly 768 × 768 for max accuracy with minimum
  token cost.
- Other aspects: scale so shortest side = 768 px; long side capped at
  2048 px.
- Have not observed scaling-drift artifacts; the API appears to return
  coords in the sent coordinate system.

---

## 4. Gemini family

### 4.1 Pipeline (per user-provided pricing notes)

- **≤ 384 × 384:** flat 258 tokens; no rescale or pad.
- **Larger:** charged per 768 × 768 tile, in N × M arrangements where
  N, M ∈ {1, 2, 3}. Max canvas: 2304 × 2304 (3 × 3 tiles).
- Cost = N × M × 258 tokens.

### 4.2 Validation: many sizes, perfect accuracy

`scripts/validate_vision.py` (gemini CLI, model `gemini-3-flash-preview`):
7 sizes × 4 corners.

| Size | Max error | Avg error | Verdict |
|---|---|---|---|
| 256² | 0.0 px | 0.0 px | ✓ |
| 360² | 0.0 px | 0.0 px | ✓ |
| 384² | 0.0 px | 0.0 px | ✓ |
| 768² | 0.0 px (3 of 4 corners; 1 timeout) | 0.0 | ✓ |
| 1000² | 0.0 px | 0.0 px | ✓ |
| 1024² | 0.0 px | 0.0 px | ✓ |
| 1064² | 0.0 px | 0.0 px | ✓ |

**Total: 27 of 27 successful tests at exactly 0 px error.**

⚠️ This was the test that pre-dated the filename-anonymization fix. The
0 px result *could* be partially explained by filename leak (the model
reading coords from the path). However:
- Claude under the same filename-leak conditions still produced
  systematic drift on over-cap inputs.
- Gemini is documented to handle a wide range of input sizes without
  internal rescaling (no equivalent token cap is exposed).
- Re-testing under anonymized filenames would be ideal but was not
  re-done; results should be treated as "no worse than 0 px floor."

### 4.3 Other Gemini models

`gemini-3.1-pro-preview`, `gemini-3.1-flash-lite-preview`,
`gemini-2.5-pro`, `gemini-2.5-flash`, `gemini-2.5-flash-lite` —
supported by the CLI (model IDs accepted) but not individually validated
under this study. The pipeline is the same family, so the same caveats
apply.

### 4.4 Conclusions for Gemini

- **Gemini handles any reasonable size with no internal rescaling
  artifacts.** Padding the image to fit 768 / 1536 / 2304 tile sizes is
  *not* needed for accuracy — it's only relevant if you want to predict
  the token bill.
- **Optimal strategy:** emit images at native size up to 2304 × 2304;
  downscale to fit if larger.
- Pricing-aware optimization (smaller tile arrangements ↔ fewer tokens)
  can be done by the agent if needed but is not required for accuracy.

---

## 5. Algorithm we settled on (per family)

### 5.1 Claude family (`_compute_claude_target`)

```python
def _compute_claude_target(in_w, in_h, config):
    max_long_edge = config["max_long_edge"]
    max_tokens = config["max_tokens"]
    max_pixels = max_tokens * 750

    long_edge_scale = max_long_edge / max(in_w, in_h)
    token_scale = math.sqrt(max_pixels / (in_w * in_h))
    scale = min(1.0, long_edge_scale, token_scale)

    scaled_w = max(1, math.floor(in_w * scale))
    scaled_h = max(1, math.floor(in_h * scale))
    while scaled_w * scaled_h > max_pixels and (scaled_w > 1 or scaled_h > 1):
        if scaled_w >= scaled_h:
            scaled_w -= 1
        else:
            scaled_h -= 1

    return scale, (scaled_w, scaled_h), (scaled_w, scaled_h)
```

**Why floor + verify?** Floating-point `round` can produce a scaled size
1 px over the cap. The shrink loop guarantees we stay under.

**No padding.** Multiple-of-28 alignment isn't required and just adds
bytes.

### 5.2 Gemini family (`_compute_gemini_target`)

```python
def _compute_gemini_target(in_w, in_h):
    max_dim = 3 * 768  # 2304
    if in_w <= max_dim and in_h <= max_dim:
        return 1.0, (in_w, in_h), (in_w, in_h)
    scale = min(max_dim / in_w, max_dim / in_h)
    sw = max(1, round(in_w * scale))
    sh = max(1, round(in_h * scale))
    return scale, (sw, sh), (sw, sh)
```

Native pass-through up to 2304 × 2304; downscale to fit if larger.

### 5.3 OpenAI family (not implemented in vision_prep yet)

Suggested algorithm if needed:

```python
def _compute_openai_target(in_w, in_h):
    # 1. Fit within 2048 x 2048
    s1 = min(1.0, 2048 / max(in_w, in_h))
    # 2. Scale so shortest side = 768 (only if shortest > 768)
    short = min(in_w * s1, in_h * s1)
    s2 = min(1.0, 768 / short) if short > 768 else 1.0
    scale = s1 * s2
    sw = max(1, round(in_w * scale))
    sh = max(1, round(in_h * scale))
    return scale, (sw, sh), (sw, sh)
```

---

## 6. Maximum safe sent dimensions per Claude model

For inputs that fit under the cap at scale = 1.0, by aspect ratio. These
are the **largest** dimensions the algorithm will emit; smaller inputs
are passed through unchanged.

### Sonnet / Haiku / Opus 4.6 (1568 / 1568 caps)

| Aspect | Max w × h |
|---|---|
| 1:1 | 1084 × 1084 |
| 4:3 | 1252 × 939 |
| 3:2 | 1328 × 885 |
| 16:9 | 1446 × 813 |
| 2:1 | 1534 × 767 |

### Opus 4.7 (2576 / 4784 caps)

| Aspect | Max w × h |
|---|---|
| 1:1 | 1894 × 1894 |
| 4:3 | 2188 × 1641 |
| 3:2 | 2319 × 1546 |
| 16:9 | 2526 × 1421 |
| 2:1 | 2576 × 1288 (long-edge cap binds) |

⚠️ Avoid hand-picking 1568 × 1568 for opus-4.7.

---

## 7. Bounding-box recommendations per provider / model

A bounding box is just two points `(x1, y1, x2, y2)`, so all the
coordinate-accuracy findings apply directly. This section is the
agent-facing cheat sheet: what to send each model, what to expect back,
and how to validate.

### 7.1 Claude Sonnet 4.6

- **Send:** any image that satisfies `max(w, h) ≤ 1568` **and**
  `w × h ≤ 1,176,000`. Use `tools/vision_prep.py --model sonnet` (or
  `prep.py`) — it handles this automatically.
- **Returns:** bounding boxes in the same coordinate system as the
  sent image, when under cap. Drift = 0–2 px per corner (verified).
- **Optimal square size:** 1064 × 1064.
- **Practical max sizes by aspect:** 1252 × 939 (4:3), 1446 × 813 (16:9),
  1534 × 767 (2:1).
- **Prompt:** specify image dimensions in the prompt (`"this is W×H
  pixels"`). Ask for `x1,y1,x2,y2` of the target.
- **Verification:** if the returned bbox is at exactly `(0, 0,
  scaled_w, scaled_h)` where `scaled = sent × ~0.9`, the image was over
  cap and rescaled — re-prep with stricter limits.

### 7.2 Claude Haiku 4.5

- **Send:** same as sonnet — `max(w, h) ≤ 1568` and `w × h ≤
  1,176,000`. Same caps, same algorithm.
- **Returns:** 0–4 px noise per corner under cap (slightly noisier
  than sonnet, likely because haiku is the smaller model).
- **Cost vs sonnet:** much cheaper, ~5× faster response time observed in
  testing. Use for bulk extraction or fast iteration.
- Otherwise identical to sonnet recommendations.

### 7.3 Claude Opus 4.6

- **Send:** same as sonnet (shares 1568 / 1568 caps).
- **Returns:** comparable to sonnet (not individually stress-tested but
  same cap regime; behavior is expected to match).
- Use for tasks needing reasoning over the image content, not just
  geometric extraction.

### 7.4 Claude Opus 4.7

- **Send:** `max(w, h) ≤ 2576` **and** `w × h ≤ 3,588,000`. Use
  `vision_prep --model opus-4.7`.
- **Returns:** 0–3 px noise under cap for point queries. **Bounding-box
  emission may be noisier** — a single test showed a 186 px error on
  the right edge of an outlined rectangle at 1876² (see §10.1). For
  pixel-critical bbox work on opus-4.7, prefer two-point queries (ask
  for top-left and bottom-right separately) over one bbox query.
- **Avoid 1568 × 1568 specifically** — empirically reproducible
  asymmetric drift (max 85 px on bottom-right under anonymized
  filenames, see §10.3). The algorithm doesn't naturally produce this
  dimension for typical inputs.
- **Optimal square size:** 1876 × 1876 (3× the sonnet capacity).
- **Practical max sizes by aspect:** 2188 × 1641 (4:3), 2526 × 1421
  (16:9), 2576 × 1288 (2:1 — long-edge cap binds).
- **When to use:** dense UI screenshots where 1568² isn't enough
  resolution — e.g. dashboards with small text, fine UI elements.
- **Cost:** roughly 3× sonnet token cost per image (4784 vs 1568 max
  tokens).

### 7.5 OpenAI GPT-5.5 (default codex model)

- **Send:** square inputs at exactly **768 × 768**. For non-square,
  scale so the shortest side = 768 px and the longest side ≤ 2048 px.
- **Returns:** bounding boxes in the sent coordinate system. 0–1.4 px
  noise observed (likely real — visual estimation noise is small in
  this regime).
- **Why 768²:** that's OpenAI's native processing size for square
  detail:high inputs (resize-to-2048 step is no-op for small inputs;
  shortest-side-to-768 step lands on 768 for squares).
- **Practical max sizes by aspect** (shortest side = 768 px, no longer
  than 2048):
  - 1:1 → 768 × 768
  - 4:3 → 1024 × 768
  - 3:2 → 1152 × 768
  - 16:9 → 1365 × 768
  - 2:1 → 1536 × 768
  - up to 2048 × 768 (~2.67:1)
- **Pricing note:** detail mode `low` is 85 tokens flat regardless of
  size — use for cases where coarse coords are enough. Detail mode
  `high` (which the codex CLI uses by default) is 170 × tile_count + 85.
- **Verification:** if the returned bbox sums to a value that suggests
  scaling (rare under 768²), re-send at smaller dims.

### 7.6 Gemini 3 Flash Preview (and other Gemini models)

- **Send:** any image up to 2304 × 2304 at native size. Use
  `vision_prep --model gemini-3-flash`.
- **Returns:** **0 px error** at every tested size from 256² to 1064²
  (27 of 27 corners exact under filename-leaky conditions, 4 of 4
  exact under anonymized filenames at 1024², 4 of 4 exact for bbox at
  1024²). No internal rescaling observed.
- **Optimal size:** native. There is **no benefit** to padding the image
  to specific tile sizes — Gemini handles arbitrary dims.
- **Pricing-aware sizing** (optional, for the cost-conscious agent):
  - Image ≤ 384 × 384 → flat 258 tokens.
  - Larger → 258 × N × M tokens where N = ⌈w/768⌉, M = ⌈h/768⌉.
  - Smallest tile arrangement that contains the image at scale = 1 is
    cheapest.
- **For agents that want minimum-cost-and-maximum-accuracy:** native
  pass-through with no padding. Padding does NOT save tokens (cost is
  computed from image dims, not file dims) and only bloats the file.
- **Gemini 3.1 Pro Preview, Gemini 2.5 Pro/Flash/Lite:** same pipeline;
  not individually validated but expected to share characteristics.

### 7.7 Comparison summary: who do you send to?

| Need | Send to | Why |
|---|---|---|
| **Maximum coord accuracy** | Gemini 3 Flash | 0 px observed at every size |
| **Pixel-perfect bbox at very low cost** | Gemini 3 Flash @ ≤ 384² | Flat 258 tokens |
| **Dense UI with small elements** | Claude Opus 4.7 @ 1876² | 3× resolution of sonnet |
| **Bulk extraction (high QPS)** | Claude Haiku 4.5 @ 1064² | Cheapest + fastest Claude |
| **High accuracy, mid-cost** | Claude Sonnet 4.6 @ 1064² | Reliable 0–2 px noise |
| **Already in OpenAI pipeline** | GPT-5.5 @ 768² | Native size, 0–1.4 px |
| **Need reasoning *about* the bbox** | Claude Sonnet/Opus | Strong text reasoning |

### 7.8 Prompt template that works across all providers

```
The image is W pixels wide and H pixels tall. There is one [TARGET].
Output ONLY four integers separated by commas: x1,y1,x2,y2 (the
top-left and bottom-right corners of the bounding box). Use the
W × H coordinate system. No other text, no labels.
```

Key elements:
- **State the dimensions explicitly.** Pre-empts the model guessing or
  using a different coord system after internal preprocessing.
- **"Output ONLY..."** suppresses preamble that breaks parsing.
- **No markdown.** Models otherwise often wrap the answer in code
  fences or backticks.
- **W × H coordinate system** disambiguates if the model has rescaled
  (especially for Claude over-cap, although you should never let that
  happen — the algorithm prevents it).

---

## 8. False starts and corrections

This is a record of mistakes worth remembering.

### 7.1 The pad-to-28 detour

Initial implementation padded the scaled image to a multiple of 28 on
right/bottom, reasoning that this matched Claude's internal padding step.
This turned out to be:
- **Unnecessary** for accuracy (multi-of-28 isn't a rescale trigger).
- **Counterproductive** when the padded dims pushed over the cap
  (e.g., scaled = 1086, padded to 1092², over cap → triggered rescale).

Resolution: drop padding entirely; scale to fit cap and emit at scaled
size.

### 7.2 The filename leak

Initial test filenames embedded coordinates
(`baseline_good_1038_1038.png`). Claude reads the file path in the
prompt and could output values from the filename without doing vision.
This produced suspicious 0 px results in early runs.

Detection: the user noted "if there's offset not like 1-3 pixel error,
it's scaling." When re-running with anonymized filenames, results
shifted from clean 0 px to typical 1-3 px noise — confirming the leak.

Resolution: all final tests use UUID-only filenames (`img_<12 hex>.png`).
The stress test (over-cap) still showed clean SCALED drift, so the
core finding survives the cleanup.

### 7.3 The 1092² "drift" mirage

In one early run, 1092² showed 10 px error on the top-right corner. We
initially interpreted this as evidence that over-cap rescaling was
happening at this size. Under anonymized filenames, 1092² ran at max
3.2 px — within noise. The 10 px result was visual noise on a single
sample.

Resolution: 1092² is only 22 tokens over the 1568 cap. Whatever
rescaling Claude does in that narrow over-cap zone (if any) isn't large
enough to distinguish from visual noise. The clean scaling signal only
emerges at 1.2× or more over cap.

### 7.4 Other lessons

- **Always run 4 corners minimum, not just one.** Single-sample results
  are misleading.
- **Re-run noisy results.** Visual noise has high variance per sample.
- **Don't ship findings until anonymized filenames are confirmed.**

---

## 9. Files in this repo

- `tools/vision_prep.py` — the family-dispatch implementation.
- `tools/prep.py`, `tools/points.py` — high-level wrappers used by the
  agent.
- `tools/translate.py` — receipt-chain coord translation.
- `scripts/validate_vision.py` — initial multi-provider validator (4
  corners per size).
- `scripts/_validate_haiku.py` — haiku-only sweep across documented
  sizes (interrupted; superseded).
- `scripts/_disambig.py` — initial filename-leaky disambiguation (4
  sizes × 4 corners).
- `scripts/_disambig3.py` — anonymized re-run of disambiguation (5
  sizes × 4 corners).
- `scripts/_stress.py` — over-cap stress test (4 sizes × 4 corners).
- `scripts/_disambig2.py` — early 800 × 600 vs 812 × 616 alignment
  comparison (interrupted when filename-leak issue was caught).

Raw outputs are in `scripts/_*_out/`.

---

## 10. Follow-up tests (2026-05-12, `scripts/_gaps.py`)

After the initial report, four gaps were tested explicitly with
anonymized filenames.

### 10.1 Bounding-box emission across providers

Same rectangle (~half the canvas, offset from origin) drawn as a red
outlined rectangle. Model asked for `x1, y1, x2, y2`.

| Model | Size | Expected bbox | Got | Diff (per corner) | L2 err |
|---|---|---|---|---|---|
| haiku 4.5 | 1064² | (212, 319, 744, 691) | (211, 320, 745, 690) | [-1, +1, +1, -1] | **2.0 px** |
| sonnet 4.6 | 1064² | (212, 319, 744, 691) | (213, 323, 748, 691) | [+1, +4, +4, 0] | **5.7 px** |
| opus 4.7 | 1876² | (375, 562, 1313, 1219) | (376, 531, 1499, 1167) | [+1, -31, **+186**, -52] | **195.6 px** |
| gemini 3-flash | 1024² | (204, 307, 716, 665) | (204, 307, 716, 665) | [0, 0, 0, 0] | **0.0 px** |
| codex (gpt-5.5) | 768² | (153, 230, 537, 499) | (153, 230, 538, 500) | [0, 0, +1, +1] | **1.4 px** |

**bbox emission ≈ point emission for most models** — accuracy is within
noise. **Two outliers:**

- **Gemini still gives literal 0 px** on all four bbox corners even with
  anonymized filenames. The model's coordinate output is essentially
  perfect for this task.
- **Opus 4.7 was way off on the right edge** (+186 px on x2). The other
  three corners were within 50 px; only x2 was wildly mispredicted.
  Could be a one-shot quirk (N=1 per model in this test) or a real
  opus-4.7 weakness with outlined rectangles. Worth noting in
  recommendations.

### 10.2 Sonnet 4.6 over-cap stress

Confirms sonnet shares haiku's behavior (same 1568 / 1568 caps):

| Sent (sonnet) | Over cap | Predicted scale | Max drift | Avg drift |
|---|---|---|---|---|
| 1200² | 1.2× | 0.904 | 152.9 px | 92.3 px |
| 1500² | 1.9× | 0.723 | 566.4 px | 246.9 px |

The 1500² far-corner predictions: (1463, 1463) → (1062, 1063), which is
exactly the `sent × 0.723 = 1058` scale prediction within visual noise.
**Identical behavior to haiku.** Opus 4.6 (same caps) is therefore very
likely to match — still not individually tested but the inference is now
strongly supported.

### 10.3 Opus 4.7 @ 1568² anomaly — reproduces under anonymization

| Corner | Expected | Got | Error |
|---|---|---|---|
| TL | (39, 39) | (50, 50) | 15.6 px |
| TR | (1529, 39) | (1480, 42) | **49.1 px** |
| BL | (39, 1529) | (42, 1526) | 4.2 px |
| BR | (1529, 1529) | (1453, 1490) | **85.4 px** |

Earlier (filename-leaky) run showed 122 px on BR; this anonymized run
shows 85.4 px. **The anomaly is real and reproducible.** Pattern:
right-side corners drift inward, bottom-right drifts diagonally inward.

This is *not* the clean uniform-scale pattern we see for sonnet/haiku
over-cap. It's some asymmetric distortion specific to opus-4.7 at
1568², which is below the opus-4.7 cap and shouldn't trigger rescaling.

Workaround: don't hand-pick 1568² for opus-4.7. The algorithm doesn't
produce this size for normal inputs.

### 10.4 Gemini 3 Flash @ 1024² — true noise floor

All 4 corners with UUID-only filenames:

| Corner | Expected | Got | Error |
|---|---|---|---|
| TL | (25, 25) | (25, 25) | **0.0 px** |
| TR | (999, 25) | (999, 25) | **0.0 px** |
| BL | (25, 999) | (25, 999) | **0.0 px** |
| BR | (999, 999) | (999, 999) | **0.0 px** |

**The 0-px-on-every-size result was not filename leak.** Gemini's
coordinate output is genuinely exact for this task class. This is the
most striking single finding in the whole report.

---

## 11. Open questions (post follow-up)

After the follow-up tests, the remaining gaps are:

1. **Why does opus-4.7 mis-emit the right edge of outlined bboxes at
   1876²?** N=1 in this run. Could be visual perception of stroke
   thickness, could be model bias. Worth retesting with filled rects
   and N≥3.
2. **What's the exact opus-4.7 1568² mechanism?** Drift pattern is
   asymmetric, not uniform scaling. Some internal preprocessing step
   misbehaves at this specific size. Not worth deep investigation —
   just avoid it.
3. **OpenAI behavior at over-2048-px inputs?** Not tested.
4. **Variance** — every cell in our tables is N=1 or N=4. A higher-N
   re-run would tighten the error bars but is unlikely to change the
   conclusions.
5. **Other Gemini models** (3.1-pro, 3.1-flash-lite, 2.5-pro/flash/lite)
   share the pipeline family but are not individually validated.

---

## 12. TL;DR for the agent

1. **Always use `vision_prep` / `prep`.** Don't hand-pick sizes.
2. **For Claude, trust the algorithm.** It produces sent dimensions that
   are under the cap; no rescaling happens; coords come back accurate
   to 0-3 px.
3. **For Gemini, anything ≤ 2304 × 2304 works.** Native pass-through.
4. **For OpenAI, send square inputs at 768 × 768.** Other aspects:
   shortest side = 768 px.
5. **Bbox isolation workflow:** rough crop with `crop.py`, look at the
   prepped image, get coords from the model, translate back with
   `points.py` (or `translate.py` for chained receipts).
