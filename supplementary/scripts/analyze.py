"""Compute the paper's numbers from the filled annotation / rating sheets (read-only, stdlib only).

Usage:  python eval/analyze.py
Inputs in Paper Publication/eval_data/:
    annotation/key.csv, annotator_A.csv (labels filled), annotator_B.csv (subset, labels filled)
    optional column `final` in annotator_A.csv = adjudicated label after A/B disagreement discussion
    optional ratings.csv     rater_id,item_code,clarity,brand_fit,appeal[,tts_mos]
    optional rating_key.csv  item_code,condition,slug
Output: results.md (also printed).
"""
from __future__ import annotations

import csv
import math
import random
import statistics as st
from collections import defaultdict

from common import EVAL_DATA

ANN = EVAL_DATA / "annotation"
R = random.Random(11)


def read(p):
    with open(p, newline="", encoding="utf-8-sig") as f:
        return list(csv.DictReader(f))


def wilson(k, n, z=1.96):
    if n == 0:
        return (float("nan"),) * 2
    p = k / n
    d = 1 + z * z / n
    c = (p + z * z / (2 * n)) / d
    h = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n)) / d
    return c - h, c + h


def pct(x):
    return f"{100*x:.1f}%"


def cohen_kappa(a, b):
    n = len(a)
    po = sum(x == y for x, y in zip(a, b)) / n
    ca, cb = defaultdict(int), defaultdict(int)
    for x, y in zip(a, b):
        ca[x] += 1; cb[y] += 1
    pe = sum(ca[k] * cb[k] for k in set(ca) | set(cb)) / (n * n)
    return (po - pe) / (1 - pe) if pe < 1 else 1.0, po


def boot_ci(per_product_fn, products, reps=4000):
    vals = []
    for _ in range(reps):
        samp = [R.choice(products) for _ in products]
        vals.append(per_product_fn(samp))
    vals = [v for v in vals if v == v]
    vals.sort()
    return vals[int(.025 * len(vals))], vals[int(.975 * len(vals)) - 1]


def sign_test_p(pos, neg):
    n = pos + neg
    if n == 0:
        return 1.0
    k = min(pos, neg)
    return min(1.0, 2 * sum(math.comb(n, i) for i in range(k + 1)) / 2 ** n)


def main():
    out = []
    key = {r["item_id"]: r for r in read(ANN / "key.csv")}
    A = read(ANN / "annotator_A.csv")
    lab = {}
    for r in A:
        l = (r.get("final") or r["label"]).strip().upper()
        if l:
            lab[r["item_id"]] = l
    out.append(f"## Claim annotation\n\n- items labelled by A: {len(lab)} of {len(A)}")

    # per-condition stats (X = not a factual claim, excluded)
    rows = []
    for iid, l in lab.items():
        if l == "X":
            continue
        k = key[iid]
        rows.append(dict(slug=k["slug"], cond=k["condition"], unsup=int(l in "CN"),
                         contra=int(l == "C"), utype=k["unit_type"],
                         auto_miss=bool(k["auto_missing"].strip())))
    out.append("\n| condition | factual claims | supported | not in source | contradicted | unsupported rate (Wilson 95% CI) | unsupported (product-cluster bootstrap CI) |\n|---|---|---|---|---|---|---|")
    conds = sorted({r["cond"] for r in rows})
    prods = sorted({r["slug"] for r in rows})
    per = {}
    for c in conds:
        rs = [r for r in rows if r["cond"] == c]
        n = len(rs); u = sum(r["unsup"] for r in rs); cn = sum(r["contra"] for r in rs)
        lo, hi = wilson(u, n)

        def f(samp, c=c):
            rr = [r for s in samp for r in rows if r["slug"] == s and r["cond"] == c]
            return sum(r["unsup"] for r in rr) / len(rr) if rr else float("nan")
        blo, bhi = boot_ci(f, prods)
        out.append(f"| {c} | {n} | {n-u} | {u-cn} | {cn} | {pct(u/n)} [{pct(lo)}, {pct(hi)}] | [{pct(blo)}, {pct(bhi)}] |")
        per[c] = {s: (sum(r['unsup'] for r in rs if r['slug'] == s), sum(1 for r in rs if r['slug'] == s)) for s in prods}

    if len(conds) == 2:
        c1, c2 = conds
        diffs = []
        for s in prods:
            (u1, n1), (u2, n2) = per[c1][s], per[c2][s]
            if n1 and n2:
                diffs.append(u1 / n1 - u2 / n2)
        pos = sum(d > 0 for d in diffs); neg = sum(d < 0 for d in diffs)
        out.append(f"\nPaired by product ({c1} minus {c2}, unsupported rate): mean diff {100*st.mean(diffs):+.1f} pp over "
                   f"{len(diffs)} products; {c1} worse in {pos}, better in {neg}, tied {len(diffs)-pos-neg}; "
                   f"two-sided sign test p = {sign_test_p(pos, neg):.3f}.")

    # self-reported provenance check (proof points)
    pp = [(iid, l) for iid, l in lab.items() if key[iid]["unit_type"] == "proof_point" and l != "X"]
    if pp:
        for c in conds:
            sub = [l for iid, l in pp if key[iid]["condition"] == c]
            if sub:
                s = sum(l == "S" for l in sub)
                out.append(f"- proof points in {c}: {len(sub)}; supported {s} ({pct(s/len(sub))}); "
                           f"each carries an LLM-written 'source' string, so provenance label != verification")

    # automatic numeric check vs human numbers_ok
    hum = {r["item_id"]: r["numbers_ok"].strip().upper() for r in A if r.get("numbers_ok", "").strip()}
    both = [(iid, h) for iid, h in hum.items() if h in ("Y", "N")]
    if both:
        agree = sum((h == "N") == bool(key[iid]["auto_missing"].strip()) for iid, h in both)
        out.append(f"- numeric check: human `numbers_ok` vs automatic number-in-record test agree on {agree}/{len(both)} items "
                   f"({pct(agree/len(both))}); items humans flagged N: {sum(h=='N' for _,h in both)}")

    # inter-annotator agreement
    B = read(ANN / "annotator_B.csv") if (ANN / "annotator_B.csv").exists() else []
    a_l, b_l = [], []
    A_raw = {x["item_id"]: x["label"].strip().upper() for x in A}  # raw (pre-adjudication) labels of A
    for r in B:
        bl = r["label"].strip().upper()
        if bl and A_raw.get(r["item_id"]):
            a_l.append(A_raw[r["item_id"]]); b_l.append(bl)
    if a_l:
        k4, po = cohen_kappa(a_l, b_l)
        bin_a = ["U" if x in "CN" else ("S" if x == "S" else "X") for x in a_l]
        bin_b = ["U" if x in "CN" else ("S" if x == "S" else "X") for x in b_l]
        k3, po3 = cohen_kappa(bin_a, bin_b)
        out.append(f"\n## Inter-annotator agreement (A vs B, n = {len(a_l)} items)\n\n"
                   f"- 4-label Cohen's kappa = {k4:.2f} (raw agreement {pct(po)})\n"
                   f"- 3-label (Supported / Unsupported / Not-a-claim) kappa = {k3:.2f} (raw agreement {pct(po3)})")

    # ratings
    rp, kp = EVAL_DATA / "ratings.csv", EVAL_DATA / "rating_key.csv"
    if rp.exists() and kp.exists():
        rk = {r["item_code"]: r for r in read(kp)}
        rt = read(rp)
        dims = [d for d in ("clarity", "brand_fit", "appeal", "tts_mos") if d in rt[0]]
        out.append(f"\n## Human ratings (1-5)\n\n- raters: {len({r['rater_id'] for r in rt})}; ratings: {len(rt)}\n")
        out.append("| dimension | " + " | ".join(sorted({v['condition'] for v in rk.values()})) + " |\n|---|" + "---|" * len({v['condition'] for v in rk.values()}))
        for d in dims:
            cells = []
            for c in sorted({v["condition"] for v in rk.values()}):
                xs = [float(r[d]) for r in rt if r.get(d, "").strip() and rk.get(r["item_code"], {}).get("condition") == c]
                if not xs:
                    cells.append("-"); continue
                bs = sorted(st.mean(R.choices(xs, k=len(xs))) for _ in range(3000))
                cells.append(f"{st.mean(xs):.2f} [{bs[75]:.2f}, {bs[2925]:.2f}] (n={len(xs)})")
            out.append(f"| {d} | " + " | ".join(cells) + " |")

    text = "\n".join(out)
    (EVAL_DATA / "results.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
