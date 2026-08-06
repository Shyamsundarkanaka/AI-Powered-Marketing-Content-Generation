# Radboards — Visual Identity

Everything in this document is applied by [`media/movie.py`](../media/movie.py), which
reads the `visual` block of [`brand.yaml`](./brand.yaml) at render time. Change a hex
value or a safe-area number there and the next rendered video picks it up — there is no
hard-coded colour anywhere in the renderer.

## Palette

| Token | Hex | Used for |
|---|---|---|
| `ink` | `#0B0E14` | Base background, letterbox fill behind photography |
| `surface` | `#151C28` | Lower-third plates, spec cards |
| `primary` | `#FF5A1F` | CTA, the one key number per scene, progress bar |
| `accent` | `#17E0C4` | Spec labels, secondary highlights, underline rules |
| `paper` | `#F5F7FA` | Primary text on dark |
| `muted` | `#9AA7B8` | Secondary text, captions under a headline |

**The one-accent rule.** Exactly one element per scene may be `primary`. If the
headline is orange, the CTA chip is not. Orange marks the thing you want read first,
and it stops working when everything is orange.

Scraped product photography is shot on white by the manufacturer, so every image sits
on `ink` with a bottom-up gradient scrim (`gradient_scrim`) to keep text legible over
the lighter part of the frame.

## Typography

| Role | Family | Fallback chain | Treatment |
|---|---|---|---|
| Display | Bahnschrift | Impact → Arial Bold → DejaVu Sans Bold | Uppercase, +2px tracking |
| Body | Segoe UI | Arial → DejaVu Sans | Sentence case, normal tracking |

The renderer resolves fonts through the candidate list in `brand.yaml` and falls back
gracefully, so a machine without Bahnschrift still produces a correct-looking video
rather than crashing.

Display type is uppercase with positive tracking because it is read at arm's length on
a phone, in motion, usually muted. Body type is sentence case because uppercase body
copy is slower to read and reads as shouting — which is off-voice.

## Video format

Vertical **1080 × 1920**, 30 fps, 25–32 seconds. This is the Reels / Shorts / TikTok
native frame; anything else gets letterboxed by the platform and loses attention.

### Safe areas

| Edge | Reserved px | Why |
|---|---|---|
| Top | 220 | Platform header, account handle |
| Bottom | 380 | Caption block, action rail, audio strip |
| Left / right | 72 | Action buttons, general breathing room |

No text is ever placed inside these bands. The renderer composes within the remaining
box, so a headline cannot land under the Instagram UI.

### Motion

**Ken Burns on every photographic scene.** Zoom from 1.06 to 1.18 with up to 90px of
pan, eased in and out — never linear, because a linear zoom reads as a slideshow
artifact rather than as camera movement. Direction alternates scene to scene so the
video does not feel like it is drifting one way for 30 seconds.

**Transitions** are 0.45s cross-dissolves. No wipes, no spins, no zoom-blur. The
product is the interesting thing; the transition should not compete with it.

### Scene grammar

| Scene | Duration | Contents |
|---|---|---|
| Title card | 2.2s | Wordmark, product name, price chip |
| Feature scenes | 4–6s each | Product photo, headline, one supporting line |
| Spec callout | 4–5s | Photo with 2–3 spec pills (`accent` labels, `paper` values) |
| CTA card | 3.0s | Wordmark, CTA line, website |

A thin `primary` progress bar runs along the bottom of the safe area for the full
duration. It costs nothing and measurably holds attention — the viewer can see the end
coming.

## Logo lockup

Wordmark `RADBOARDS`, display face, uppercase, top-left, with 48px clear space on all
sides. It appears on the title card and the CTA card only — not burned into every
frame, which reads as defensive.

## What we don't do

- Purple gradients, glassmorphism, or any generic "tech product" template look
- Stock lifestyle footage that isn't the actual product
- Text over the busiest part of an image — the scrim exists so this never happens
- More than two type sizes on screen at once
