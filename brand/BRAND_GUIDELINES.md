# Radboards — Brand Guidelines

The machine-readable version of everything below lives in [`brand.yaml`](./brand.yaml),
which is what the code actually parses. This document explains the reasoning, so that
a human editing `brand.yaml` knows what they are trading away.

> **Scope note.** These guidelines were authored for this content-generation system.
> They are a working brand definition derived from Radboards' product catalogue and
> market position — not a document handed down by the company.

## 1. What Radboards is

Radboards sells personal electric rides in India: hoverboards, off-road boards and
electric unicycles. The products are priced and specced for people who want to
actually *use* them — not collect them.

**Positioning:** the dependable, genuinely fun way to cover the last three kilometres.

That sentence does real work. It rules things out:

- Not a toy brand → we never write copy that sounds like it's aimed at a 12-year-old.
- Not a luxury brand → we never lean on exclusivity, scarcity or status.
- Not a fitness brand → we make no health claims, ever (see [COMPLIANCE.md](./COMPLIANCE.md)).

## 2. Voice

**Archetype:** the Explorer, with an engineer's honesty.

The Explorer half is why the copy is about *going somewhere*. The engineer half is why
it never overclaims. A Radboards asset should read like it was written by someone who
has ridden the thing to work in the rain and will tell you exactly how that went.

### Five principles

1. **Lead with the rider's moment, not the spec sheet.** Specs are the proof, never the
   hook. "The 2.5 km your metro card doesn't cover" beats "600W dual motor".
2. **One concrete number beats three adjectives.** "45 km range" over "incredible range".
   If we cannot source a number from scraped data, we say less rather than reaching for
   an adjective.
3. **Write to one person.** Second person singular. The reader is standing next to the
   board, deciding.
4. **Earn the excitement.** Every claim traces back to something in `scraped_data`.
   No invented specs, no invented prices, no invented delivery promises.
5. **Cut every word doing no work.** Sentences cap at 18 words. Most should be shorter.

### Words we use

ride, rider, board, charge, range, grip, glide, commute — plus construction like
"built for", "made to take", "holds up to".

### Words we never use

revolutionary · game-changing · disruptive · cutting-edge · unleash · elevate ·
best-in-class · world-class · next-generation · seamless · synergy

Also banned: fake urgency ("buy before it's gone", countdown framing), competitor
names, and any comparative claim against another brand.

These bans are enforced in the prompt, not just in this document — the banned list is
injected into every generation call from `brand.yaml`.

### Tone shifts by artifact

| Artifact | Tone |
|---|---|
| Campaign brief | Analytical, plain-spoken. Written for a marketer, not a customer. |
| Script | Spoken-word energy. Short sentences a narrator can say in one breath. |
| Caption | Conversational. Sounds like a person, not a press release. |
| Hashtags | Plain lowercase. No camelCase walls, no keyword stuffing. |

## 3. Audience

Three personas, detailed in [PERSONAS.md](./PERSONAS.md). The default is
**urban-commuter** unless the product is an off-road board, in which case
**weekend-explorer** leads.

The persona choice changes the hook, not the voice. Aditya wants a minute-count.
Nikita wants a moment worth screenshotting. Rohit wants to know what the tyres survive.

## 4. Language rules

- Indian English. Grade 7 reading level.
- Sentences: 18 words maximum.
- Emoji: 1–3 in captions and only where an emoji replaces a word. Zero in scripts
  and briefs.
- Numbers are rendered **exactly as scraped**. No rounding, no unit conversion, no
  filling in a plausible-looking gap. Prices use `₹` with no decimals (₹24,999).

## 5. Per-artifact rules

These are enforced structurally — the generation graph validates against them.

**Campaign brief** — six sections: objective, target persona, key message, proof points
(minimum 3), channels, success metric. Every proof point cites a scraped spec, price or
description line.

**Script** — 25–32 seconds at ~2.4 words/second. Five beats: hook, problem, product
reveal, proof, CTA. Hook is 12 words or fewer. No stage directions inside spoken lines;
the video plan handles visuals.

**Caption** — 300 characters max. The first 70 characters must stand alone, because
that is all most people see before "…more". CTA required.

**Hashtags** — 8 to 12, lowercase, always including `#radboards`. Banned:
`#viral`, `#followforfollow`, `#likeforlike`, `#trending`, `#explorepage`.

**Video plan** — 5 to 7 scenes, one per script beat, vertical. Every scene names the
scraped image it uses by index.

## 6. Visual identity

Summarised in [VISUAL_IDENTITY.md](./VISUAL_IDENTITY.md) and applied automatically by
`media/movie.py`, which reads the `visual` block of `brand.yaml`. Changing a hex value
there changes the rendered video with no code edit.

## 7. Compliance

Non-negotiable, and separate from taste. See [COMPLIANCE.md](./COMPLIANCE.md). The short
version: say only what was scraped, never guarantee safety, never claim road-legality,
never make a health claim.
