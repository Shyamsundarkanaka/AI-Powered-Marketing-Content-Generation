"""Build a small BLIND sheet (10% of 360 = 36 units) for an independent human labelling.

Stratified: ~5 units per product, balanced between conditions, >= 2/3 factual claims (by the reviewed label) so kappa is informative.
Output: Paper Publication/eval_data/annotation/annotator_blind_36.csv  (no labels, no suggested evidence, no condition)
Usage: python eval/make_blind_sheet.py
"""
import csv, random
from common import EVAL_DATA
ANN = EVAL_DATA / "annotation"
rd = lambda f: list(csv.DictReader(open(ANN / f, encoding="utf-8-sig")))
A, K = rd("annotator_A.csv"), {r["item_id"]: r for r in rd("key.csv")}
rnd = random.Random(2026)
by = {}
for r in A: by.setdefault(r["product"], []).append(r)
pick = []
for i, (prod, rows) in enumerate(sorted(by.items())):
    n = 6 if i == 0 else 5
    fact = [r for r in rows if r["label"] in "SCN"]; non = [r for r in rows if r["label"] == "X"]
    nf = round(n * 2 / 3) + 1 if n == 6 else round(n * 2 / 3)
    # balance conditions among the factual ones
    pip = [r for r in fact if K[r["item_id"]]["condition"] == "pipeline"]; bas = [r for r in fact if K[r["item_id"]]["condition"] == "baseline"]
    rnd.shuffle(pip); rnd.shuffle(bas); rnd.shuffle(non)
    f = (pip[: nf // 2 + nf % 2] + bas[: nf // 2])[:nf]
    pick += f + non[: n - len(f)]
rnd.shuffle(pick)
with open(ANN / "annotator_blind_36.csv", "w", newline="", encoding="utf-8-sig") as f:
    w = csv.writer(f); w.writerow(["item_id", "product", "claim_text", "label", "numbers_ok", "notes"])
    for r in sorted(pick, key=lambda r: (r["product"], r["item_id"])): w.writerow([r["item_id"], r["product"], r["claim_text"], "", "", ""])
print(len(pick), "items;", sum(r["label"] in "SCN" for r in pick), "factual by reviewed label;",
      {c: sum(K[r["item_id"]]["condition"] == c for r in pick) for c in ("pipeline", "baseline")})
