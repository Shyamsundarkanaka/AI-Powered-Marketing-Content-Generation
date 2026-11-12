"""Build the blinded rater pack (read-only): 3 products x 2 conditions = 6 items, shuffled.

Usage: python eval/make_rating_pack.py
Writes Paper Publication/eval_data/rating_pack.md (send to raters / paste into a Google Form)
       Paper Publication/eval_data/rating_key.csv  (item_code,condition,slug) - KEEP PRIVATE
Part B (TTS naturalness) uses the pipeline voiceover files listed at the end of rating_pack.md.
"""
import csv, random
from common import EVAL_DATA, first_version_dirs, load_package

PRODUCTS = ["hoverboard", "e-scooter", "electric-unicycle-kingsong-14d"]
rnd = random.Random(5)
dirs = {slug: d for _, slug, d in first_version_dirs()}
items = []
for slug in PRODUCTS:
    for cond, path in (("pipeline", dirs[slug]), ("baseline", EVAL_DATA / "baseline" / f"{slug}.json")):
        items.append((slug, cond, load_package(path)))
rnd.shuffle(items)
key, md = [], ["# Rating task (about 10 minutes)\n",
    "You will read 6 short marketing packages for 3 hoverboard / scooter / unicycle products from an Indian brand called Radboards. "
    "For each, rate 1 (very poor) to 5 (excellent):\n",
    "- **Clarity**: is the message easy to follow when spoken aloud?\n- **Brand fit**: does it sound like a confident, warm, specific, never hype-y brand?\n"
    "- **Appeal**: would it make you want to look at the product?\n",
    "Rate each item on its own. No personal data is collected; give your rater ID (R1, R2, ...).\n"]
for i, (slug, cond, p) in enumerate(items, 1):
    code = f"P{i}"
    key.append(dict(item_code=code, condition=cond, slug=slug))
    md.append(f"\n---\n## Item {code}\n**Voice-over script**\n")
    for b in p["script"].get("beats", []):
        md.append(f"- {b.get('line','')}")
    md.append(f"\n**Caption**\n\n{p['caption'].strip()}\n\n**Hashtags**: {p['hashtags'].strip()}\n")
    md.append("Ratings: Clarity [1-5] ___  Brand fit [1-5] ___  Appeal [1-5] ___\n")
md.append("\n---\n# Part B - voice naturalness (3 clips)\nListen to each voice-over and rate how natural the voice sounds, 1 (robotic) to 5 (human).\n")
for k, slug in enumerate(PRODUCTS, 1):
    md.append(f"- Clip V{k}: file `{dirs[slug] / 'voiceover.wav'}`   (rate: ___)")
(EVAL_DATA / "rating_pack.md").write_text("\n".join(md), encoding="utf-8")
with open(EVAL_DATA / "rating_key.csv", "w", newline="", encoding="utf-8") as f:
    w = csv.DictWriter(f, ["item_code", "condition", "slug"]); w.writeheader(); w.writerows(key)
print(len(items), "items;", "voice clips:", [str(dirs[s] / "voiceover.wav") for s in PRODUCTS])
