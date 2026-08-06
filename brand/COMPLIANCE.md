# Radboards — Content Compliance Guardrails

These are not style preferences. A generated asset that violates anything here should
be rejected in review even if the copy is excellent.

The structured version is `compliance` in [`brand.yaml`](./brand.yaml), which is injected
verbatim into every agent prompt.

## The single rule underneath all of them

**Say only what the scraped data supports.**

Every generated claim must trace to a field in the `scraped_data` row for that product:
a spec, the price, or a line of the description. The agents are given that row and
nothing else about the product for exactly this reason — there is no other source they
could be drawing a number from.

This is also the failure mode most worth watching for in review: an LLM will happily
produce a confident, plausible, entirely invented "50 km range".

## Must

- **Price** — state it only if it was scraped. Never estimate, never anchor against a
  "was" price that isn't in the data.
- **Specs** — present verbatim. Where the source says "up to", we say "up to".
- **Safety** — phrase as a recommendation ("wear a helmet"), never as a property of the
  product ("keeps you safe").
- **Disclosure** — when a headline number is the main claim of an asset, include:
  > Range, speed and charge-time figures are manufacturer claims and vary with rider
  > weight, terrain and temperature.

## Must not

- **No invented commercial terms.** No delivery times, warranty periods, EMI options,
  discounts, coupon codes or return windows unless scraped.
- **No regulatory implication.** Never suggest a product is road-legal, insured,
  registered, or approved by any authority. Rules differ by state and we do not know
  the rider's context.
- **No health or medical claims.** Not fitness, not calories, not posture, not
  "safer than". Personal electric mobility is not a health product.
- **No injury-prevention guarantee.** Protective gear reduces risk; it does not
  eliminate it, and we never imply otherwise.
- **No targeting minors.** Copy is written for adults. No school-age framing, no
  depiction of unsupervised child riders.
- **No unprotected riding in copy.** If the copy describes a ride, gear is present.
- **No competitor references.** No brand names, no "better than", no comparison tables.

## Where each rule is enforced

| Layer | What it catches |
|---|---|
| Prompt injection (`graph/prompts.py`) | The model is told the rules before generating |
| Structured output schema (`graph/nodes.py`) | Shape and required-field violations |
| Banned-phrase check (`brand.yaml → voice.we_never_say`) | Hype vocabulary, fake urgency |
| Human review (Streamlit Output tab) | Everything else — this is the real backstop |

The first three layers reduce how often a reviewer has to reject. They do not replace
the reviewer. Approve/reject exists because generated marketing copy needs a human to
sign off before it represents the brand.

## When a version is rejected

Reviewer feedback is stored on the version row and injected into the next generation
attempt as an explicit revision directive, so the same compliance problem should not
recur on v2. If it does recur, the rule needs to move up a layer — from prose in this
file into a structural check in `graph/nodes.py`.
