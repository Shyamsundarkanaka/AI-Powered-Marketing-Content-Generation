# Radboards — Audience Personas

Three personas. Structured copies live in `brand.yaml` under `audience.personas`;
the campaign-brief agent picks one and every downstream agent inherits it.

Persona choice changes **the hook and the proof points**. It never changes the voice.

---

## 1. `urban-commuter` — Aditya, 26 *(default)*

Bengaluru. Hybrid role, in the office three days a week. The metro drops him 2.5 km
from his desk, which is the exact problem Radboards solves. Owns a motorcycle he
refuses to ride in peak traffic. Researches for about three weeks, then buys from an
Instagram ad at 11pm.

**Wants**
- A commute time he can predict to the minute
- Something he can carry up to a third-floor flat without resenting it
- Range he can trust on a Friday evening, not just on day one

**Fears**
- Being stranded at 40% battery, halfway home
- Looking silly rolling into an office lobby
- A cheap build that develops a rattle within a month

**The hook that works:** the exact minute-count of the commute, before and after.
Not "faster commute" — "18 minutes becomes 6".

**Proof points he cares about:** range, charge time, weight, build materials.

---

## 2. `campus-rider` — Nikita, 20

Engineering student on a large campus with eight-minute walks between blocks. Price
sensitive but very brand-aware. Screenshots everything into a group chat before
deciding anything.

**Wants**
- Fun, first and foremost
- Fast hops between classes
- Something that looks good in a reel

**Fears**
- A parental veto on the price
- Nowhere safe to charge in a hostel room
- Breaking it in the first week and having no recourse

**The hook that works:** speed and style framed as a *shared* moment — riding with
friends, not a solo flex. Nikita's purchase is a social decision.

**Proof points she cares about:** top speed, colourways, weight, price.

---

## 3. `weekend-explorer` — Rohit, 34 *(default for off-road products)*

Owns a car, lives in a gated township, rides for fun on Sunday mornings and brings the
kids along. Reads spec sheets properly and will notice if a number is vague.

**Wants**
- Genuine off-road capability, not a marketing word
- Real torque on inclines
- Build quality he can inspect before buying

**Fears**
- An underpowered motor that stalls on a slope
- Tyres that give up on gravel
- Water damage after one wet ride

**The hook that works:** the terrain the board can actually take, stated plainly.
Rohit is the persona most damaged by overclaiming — one inflated number and he's gone.

**Proof points he cares about:** motor wattage, tyre type and size, water resistance,
incline rating, frame material.

---

## Selecting a persona

The campaign-brief agent chooses based on the scraped product:

| Signal in scraped data | Persona |
|---|---|
| "off-road", "rover", knobbly/pneumatic tyres, high wattage | `weekend-explorer` |
| Lowest price tier, "classic", bright colourways | `campus-rider` |
| Everything else | `urban-commuter` |

The chosen persona id is written into the campaign brief and carried in pipeline
state, so the script, caption and hashtag agents all target the same person.
