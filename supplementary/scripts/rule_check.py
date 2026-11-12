"""Deterministic brand-rule compliance check of generated packages (read-only).

Usage:  python eval/rule_check.py
Compares condition C1 (pipeline output v1) and C2 (baseline json) against the numeric/lexical rules in
brand/brand.yaml. Writes Paper Publication/eval_data/rule_check.md.
Rules checked per package (R1..R12) are listed in RULES below.
"""
from __future__ import annotations

import re

from common import EVAL_DATA, first_version_dirs, load_package

BANNED_WORDS = ["revolutionary", "game-changing", "disruptive", "cutting-edge", "unleash", "elevate",
                "best-in-class", "world-class", "next-generation", "seamless", "synergy"]
BANNED_TAGS = ["#viral", "#followforfollow", "#likeforlike", "#trending", "#explorepage"]
EMOJI = re.compile("[\U0001F300-\U0001FAFF☀-➿⭐⬆️]")
ORDER = ["hook", "problem", "product_reveal", "proof", "cta"]


def words(t):
    return re.findall(r"[A-Za-z0-9₹'’\-]+", t)


def check(pkg: dict) -> dict:
    beats = pkg["script"].get("beats", []) or []
    spoken = " ".join(b.get("line", "") for b in beats)
    cap = pkg["caption"].strip()
    tags = re.findall(r"#\w+", pkg["hashtags"])
    low = (spoken + " " + cap + " " + pkg["hashtags"]).lower()
    secs = len(words(spoken)) / 2.4
    sents = [s for b in beats for s in re.split(r"(?<=[.!?])\s+", b.get("line", "")) if s.strip()]
    hook = next((b.get("line", "") for b in beats if b.get("beat") == "hook"), "")
    return {
        "R1 caption <=300 chars": len(cap) <= 300,
        "R2 caption first line <=70 chars": len(cap.split("\n")[0]) <= 70 if cap else False,
        "R3 caption emoji 1-3": 1 <= len(EMOJI.findall(cap)) <= 3,
        "R4 hashtags 8-12": 8 <= len(tags) <= 12,
        "R5 #radboards present": "#radboards" in [t.lower() for t in tags],
        "R6 no banned hashtags": not any(t in low for t in BANNED_TAGS),
        "R7 exactly 5 beats in order": [b.get("beat") for b in beats] == ORDER,
        "R8 hook <=12 words": len(words(hook)) <= 12 and bool(hook),
        "R9 script 32-40 s (2.4 words/s)": 32 * 0.95 <= secs <= 40 * 1.10,
        "R10 sentences <=18 words": all(len(words(s)) <= 18 for s in sents) and bool(sents),
        "R11 no emoji in script": not EMOJI.search(spoken),
        "R12 no banned vocabulary": not any(w in low for w in BANNED_WORDS),
    }


def main():
    res = {"pipeline": {}, "baseline": {}}
    for pid, slug, d in first_version_dirs():
        res["pipeline"][slug] = check(load_package(d))
        b = EVAL_DATA / "baseline" / f"{slug}.json"
        if b.exists():
            res["baseline"][slug] = check(load_package(b))
    slugs = sorted(set(res["pipeline"]) & set(res["baseline"]))
    rules = list(next(iter(res["pipeline"].values())))
    out = [f"## Deterministic brand-rule check ({len(slugs)} products with both conditions)\n",
           "| rule | pipeline passes | baseline passes |\n|---|---|---|"]
    tot = {"pipeline": 0, "baseline": 0}
    allpass = {"pipeline": 0, "baseline": 0}
    for r in rules:
        row = []
        for c in ("pipeline", "baseline"):
            k = sum(res[c][s][r] for s in slugs); tot[c] += k
            row.append(f"{k}/{len(slugs)}")
        out.append(f"| {r} | {row[0]} | {row[1]} |")
    for c in tot:
        allpass[c] = sum(all(res[c][s].values()) for s in slugs)
    out.append(f"\n- rule checks passed: pipeline {tot['pipeline']}/{len(rules)*len(slugs)}, baseline {tot['baseline']}/{len(rules)*len(slugs)}")
    out.append(f"- packages passing ALL {len(rules)} rules: pipeline {allpass['pipeline']}/{len(slugs)}, baseline {allpass['baseline']}/{len(slugs)}")
    import math
    def two_sided(a, b):
        n, k = a + b, min(a, b)
        return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n) if n else 1.0
    better = sum(sum(res["pipeline"][s].values()) > sum(res["baseline"][s].values()) for s in slugs)
    worse = sum(sum(res["pipeline"][s].values()) < sum(res["baseline"][s].values()) for s in slugs)
    n10 = sum(res["pipeline"][s][r] and not res["baseline"][s][r] for s in slugs for r in rules)
    n01 = sum(res["baseline"][s][r] and not res["pipeline"][s][r] for s in slugs for r in rules)
    out.append(f"- products where the pipeline passes more rules: {better}, fewer: {worse}; two-sided sign test p = {two_sided(better, worse):.3g}")
    out.append(f"- rule-level discordant pairs: pipeline-only pass {n10}, baseline-only pass {n01}; exact McNemar p = {two_sided(n10, n01):.2g} (pooled over products; product-level test is primary)")
    out.append("\nNote: the pipeline's validators enforce a subset of these in code (counts, lengths, duration, beat order); "
               "the rest are prompt-only. Pipeline outputs here are the ones that passed validation (failed jobs produce no package).")
    text = "\n".join(out)
    (EVAL_DATA / "rule_check.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
