# Claim annotation guideline (1 page)

You get a sheet with one row per sentence taken from marketing content (a script line, a caption sentence, or a "proof point") for a product, and, per product, a text file called the **record** (title, price, specs, description scraped from the store). You do not know which system wrote each sentence. Judge each sentence **only against the record**, not against what you know about the product.

For each row fill `label` with one letter:

| Label | Meaning | Example (record: "Motor: 2 x 350W Hub Motor; Gradability: 10°; Price ₹24,999") |
|---|---|---|
| **S** Supported | The record states it, or it follows directly from it. Rewording is fine. | "Twin 350W motors climb 10° slopes." |
| **C** Contradicted | The record says something different (wrong number, unit, price, feature). | "Climbs 20° slopes." |
| **N** Not in the record | Sounds plausible but the record does not say it (invented number, feature, guarantee, EMI, delivery, warranty, comparison). | "Comes with a 1-year warranty." |
| **X** Not a factual claim | Slogan, question, invitation, brand tagline, pure opinion with no checkable content. | "Ready to leave the pavement behind?" |

Rules of thumb
- If one sentence mixes a supported and an unsupported part, label it by the **worst** part (C over N over S).
- "Up to", ranges and rounding: a number that is rounded, converted or made more precise than the record counts as **C** (the brand rule is "render specs exactly as scraped").
- Generic benefit language ("a smooth ride") that restates the description's own wording is **S**; new specifics are not.
- A price counts as supported only if it equals the record's price (or compare-at price).

Column `numbers_ok` (only if the sentence contains a number, price, unit or material): **Y** every one matches the record, **N** at least one does not, leave empty if there is none.

Column `notes`: optional; one line for tricky decisions.

Do not discuss labels with the other annotator until both have finished. Disagreements are then settled by discussion and the agreed label goes in a column named `final`.
