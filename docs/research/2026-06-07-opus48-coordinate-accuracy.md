# Claude Opus 4.8 — image size, padding & coordinate accuracy

**Date:** 2026-06-07
**Model under test:** `claude-opus-4-8` (high-res tier; same vision caps as Opus 4.7)
**Method:** red-dot localization — generate a white image with one red dot at a
known position, send it **blind** (no dimensions in the prompt, neutral
filename so the path can't leak the answer), ask for the dot's pixel
coordinates, score Euclidean error against ground truth.
**Harness:** `skills/image-cut/scripts/validate_vision.py` (+ ad-hoc sweeps).
Real API calls via the `claude` CLI.

> **Scope / caveats.** Single model (4.8), synthetic stimulus (one red dot on
> white), small N per cell (2–3 reps). Numbers are indicative, not
> publication-grade. The *direction* of every effect below reproduced across
> runs; the exact px values carry a few px of run-to-run noise.

---

## 1. The caps (confirmed)

Opus 4.7 and 4.8 share the high-res vision pipeline (per Anthropic docs, and
validated here):

| limit | value |
|---|---|
| max long edge | **2576 px** |
| max tokens | **4784** (≈ `w·h / 750`) |
| max pixels | **3,588,000** (≈ 1894² for a square) |
| internal padding | bottom/right up to a **multiple of 28** |

Other models (sonnet/haiku/opus-4.6): 1568 px / 1568 tokens.

Over-cap images are silently downscaled; coordinates then degrade linearly
(measured 10 % → 24 % → 48 % error at 2048² / 2304² / 2576²). The processed
canvas was observed to saturate at ~1905 px (≈ 28×68) for square inputs.

**4.8 vs 4.7** at 1876² (7 positions): 4.8 mean **15 px** vs 4.7 **37 px** — 4.8
roughly halves 4.7's localization error and lacks 4.7's documented
right-edge/outlined-bbox weakness.

---

## 2. The dominant effect: **coordinate magnitude**, not canvas size

The single most important finding. Error is driven by *how large the coordinate
numbers are*, ~independent of the canvas size.

Same dot at **(964,964)**, canvas grown by white padding:

| canvas | dot relative pos | mean err |
|--:|--:|--:|
| 1024² | 94 % (near edge) | 1.4 px |
| 1280² | 75 % | 1.3 px |
| 1456² | 66 % | 2.5 px |
| 1894² | 50 % (near center) | 3.6 px |

Growing the canvas to the **max square barely moved the error** — because the
coordinate stayed ~964. Contrast: on a fixed 1894² canvas, moving the dot *out*
to large coordinates:

| dot coordinate | err |
|--:|--:|
| ~964 | 3.6 px |
| ~1394 | 16 px |
| ~1694 | 76 px |
| ~1844 | 178 px |

And padding **cannot** rescue a large coordinate — at a fixed 1894² canvas,
even 200 px of margin around a corner dot left **76 px** error; 500 px → still
16 px. Padding the far edge doesn't shrink the coordinate number.

**Implication:** keep your point of interest at **small coordinates**. A big
padded canvas is fine for top-left content; the bottom-right (large x,y) of a
big canvas is the poison.

---

## 3. The size sweet spot: **768 px long edge**

Bottom-right corner, 50 px margin, 3 reps:

| emitted | corner coord | mean err | err % |
|--:|--:|--:|--:|
| 180 | 120 | 2.5 | 1.4 % |
| 260 | 200 | 4.2 | 1.6 % |
| 360 | 300 | 5.7 | 1.6 % |
| 480 | 420 | 5.3 | 1.1 % |
| 620 | 560 | 2.2 | 0.4 % |
| **768** | 708 | **1.0** | **0.1 %** |
| 900 | 840 | 1.9 | 0.2 % |

**768 is the cleanest point in the whole study** (1.0 px ×3). There is a
mediocre middle (260–480 → 4–6 px). Above ~1000 it goes **bimodal** — usually
fine but with catastrophic outliers:

| emitted | corner coord | reps | mean |
|--:|--:|--|--:|
| 1024 | 964 | 10.0, 1.4, 5.1 | 5.5 |
| 1152 | 1092 | 298, 0.0, 245 | 181 |
| 1280 | 1220 | 27.9, 303, 27.1 | 119 |
| 1456 | 1396 | 608, 29.5, 26.2 | 221 |

Past ~1100 px, coordinates are unusable (200–650 px misses, often ~half the
true value). **The high-res caps are for reading detail, never for locating.**

**Note on downscaling:** original-space error = `scaled_error ÷ scale`. Because
768's scaled accuracy (~1 px) is so much better than 900's (~1.9 px), 768 wins
on *both* counts even for big sources (e.g. 1800 px source: ~2.3 px at 768 vs
~3.8 px at 900).

---

## 4. The corner dead-zone — needs a margin (independent of size)

A target jammed against the **bottom-right edge** is localized badly,
*reproducibly*, regardless of size. The driver is proximity to the pad-to-28
boundary:

| padding to next ×28 | corner err |
|--:|--:|
| 0–1 px (exact ×28, e.g. 1876) | 25–89 px |
| ~10 px | ~34 px |
| **17–22 px** | **~0 px** |

Exact multiples of 28 are the *worst* (content corner sits on the padded edge).
A fixed white **margin** fixes it. The margin is needed even at the 768 sweet
spot:

| 768 content, corner dot | emitted | mean err |
|---|---|--:|
| no margin | 768² | **8.4 px** (7.8/9.4/8.1) |
| +50 px margin | 818² | **0.3 px** (0.0/0.0/1.0) |

Margin sweep (right edge): threshold ≈ **30 px**, **50 px optimal**, >50 no
better. Smaller (0–20 px) is erratic (~3 px with outliers).

> A search for a "calibratable offset" / grid breaking point was **refuted** —
> repeats at one position disagreed by ±12 px, i.e. the sub-threshold scatter is
> noise, not a deterministic offset. The fix is margin + (if needed)
> median-of-N, not an offset correction.

---

## 5. Tiny inputs (<~200 px) — **pad up**, don't send as-is

Tiny native images hallucinate (docs warn <200 px). Confirmed, and **padding to
a 768 canvas beats upscaling**:

| input | truth | native | upscale→768 | **pad→768** |
|--:|--:|--:|--:|--:|
| 100×50 | 70,35 | 8.6 | 1.1 | **1.0** |
| 100×200 | 70,140 | 0.0 | 0.2 | **0.0** |
| 200×300 | 140,210 | 25.0 | 0.7 | **0.5** |

Padding wins because it (a) escapes the sub-200 zone, (b) keeps coordinates
tiny (the precise zone), (c) adds **no blur** (content pixel-exact), and (d)
needs **no coordinate rescale** (coords stay native).

---

## 6. Conclusion — the settled rule

Two **independent, both-necessary** levers, plus a size target:

1. **Coordinate magnitude → keep the long edge at ~768.** Downscale bigger
   inputs; pad tiny inputs *up*. Keeps every coordinate in the rock-solid zone.
   Hard max ≈ 960; above ~1000 it's bimodal-unusable.
2. **Edge dead-zone → 50 px white margin** on right/bottom. Independent of size;
   required even at 768 (8.4 px → 0.3 px).
3. **For fine detail on a large source → crop-and-zoom**, never enlarge the
   whole canvas. Cropping the ROI keeps the target at small coordinates.

Coordinate translation: emit content at (0,0); right/bottom-only padding means
detected coords need **no offset**, only `÷ scale` when a large source was
downscaled.

| input size | action | expected error |
|---|---|--:|
| > ~900 px | downscale to 768 long edge | ~1 px (scaled); `÷scale` in original |
| ~600–900 px | as-is + 50 px margin | ~1–2 px |
| < ~600 px | pad up to 768 canvas | ~1 px |
| any, fine precision | crop ROI, send at ~768 | ~1 px |

---

## 7. Implementation

`skills/image-cut/tools/prep_claude.py` (single self-contained Claude prep tool)
implements the settled rule by default:

- `--max-edge 768` — downscale ceiling (sweet spot).
- `--min-edge 768` — pad tiny inputs up to this canvas (white, right/bottom).
- `--pad-edge-right / --pad-edge-bottom 50` — corner dead-zone margin, applied
  **after** scaling so it's an exact px amount.
- Content pasted at (0,0); receipt records `max_edge`, `min_edge`, `scale`,
  `content_size`, `scaled_content_size`, `emitted_size` for the translation
  chain.

Whatever the input, content lands in the ~768 zone, off the edge → ~1 px,
coords native.

### Supporting changes
- `vision_prep.py`: added `opus-4.8` (= 4.7 caps) to `MODEL_LIMITS`.
- `validate_vision.py`: added `opus-4.8 → claude-opus-4-8` mapping; **fixed a
  ground-truth leak** (the dot position was in the filename, which was passed to
  the model as `@path`) by using neutral indexed filenames; **removed image
  dimensions from the prompt** (stronger blind test).

---

## 8. Open follow-ups
- Quantify the margin win on **opus-4.7** specifically (the model the
  mitigation is really for; 4.8 only has the mild version).
- Validate on **real UI crops / text**, not just synthetic dots.
- More reps near the 960 hard-max to map the bimodal onset precisely.
- Post-scale vs pre-scale padding for pathological very-large downscaled sources.
