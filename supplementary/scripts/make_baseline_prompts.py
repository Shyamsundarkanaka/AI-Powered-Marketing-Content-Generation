"""Write one ready-to-paste single-prompt baseline (condition C2) per product.

Usage (from the repo root):
    python eval/make_baseline_prompts.py

Output: Paper Publication/eval_data/baseline_prompts/<slug>.txt
Paste each file into Google AI Studio with the SAME model string as the
pipeline (gemini-2.5-flash), default settings, no system prompt. Save the
reply (JSON only) as Paper Publication/eval_data/baseline/<slug>.json
One attempt only: no retries, no validators. That is the point of the baseline.
"""
from __future__ import annotations

import json
import re

from common import BRAND, EVAL_DATA, first_version_dirs, product_records

FORMAT = """\
Produce the complete marketing package for the product below as ONE JSON object
and nothing else (no markdown fences, no commentary), with exactly this shape:

{
  "campaign_brief": {
    "objective": str, "target_persona": str (one persona id from the brand file),
    "key_message": str,
    "proof_points": [ {"claim": str, "source": str} ],   // at least 3
    "channels": [str], "success_metric": str
  },
  "script": {
    "title": str,
    "beats": [ {"beat": "hook|problem|product_reveal|proof|cta", "line": str, "on_screen": str} ]
  },
  "caption": str,
  "hashtags": [str]
}

Follow the brand file's voice, language, content_rules and compliance sections
exactly. Use only facts present in the product record.
"""


def brand_text() -> str:
    txt = BRAND.read_text(encoding="utf-8")
    # drop the 'visual:' block (colours/fonts); it is not used for text generation
    txt = re.split(r"\nvisual:\n", txt)[0]
    return txt


def main():
    out = EVAL_DATA / "baseline_prompts"
    out.mkdir(parents=True, exist_ok=True)
    (EVAL_DATA / "baseline").mkdir(parents=True, exist_ok=True)
    recs = product_records()
    bt = brand_text()
    for pid, slug, _ in first_version_dirs():
        r = recs.get(pid)
        if not r:
            continue
        prod = {
            "title": r["title"], "price": r["price"], "compare_at_price": r["compare_at"],
            "description": r["description"], "specs": r["specs"],
        }
        text = (
            "You are the marketing content generator for the brand described below.\n\n"
            "=== BRAND FILE ===\n" + bt + "\n=== PRODUCT RECORD ===\n"
            + json.dumps(prod, ensure_ascii=False, indent=2) + "\n\n=== TASK ===\n" + FORMAT
        )
        (out / f"{slug}.txt").write_text(text, encoding="utf-8")
        print("wrote", out / f"{slug}.txt")


if __name__ == "__main__":
    main()
