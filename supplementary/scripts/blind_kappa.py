"""Independent agreement from the filled blind sheet (annotator_blind_36.csv) vs the reviewed labels and vs the LLM pre-labels.
Usage: python eval/blind_kappa.py   -> prints kappa with bootstrap 95% CI, writes eval_data/blind_kappa.md
"""
import csv, random
from analyze import cohen_kappa
from common import EVAL_DATA
ANN = EVAL_DATA / "annotation"
rd = lambda f: {r["item_id"]: r for r in csv.DictReader(open(ANN / f, encoding="utf-8-sig"))}
H, A, P = rd("annotator_blind_36.csv"), rd("annotator_A.csv"), rd("annotator_A.prefilled.csv")
ids = [i for i in H if H[i]["label"].strip()]
assert ids, "blind sheet is empty"
R = random.Random(3)
def kap(ref, binary=False):
    f = (lambda l: "U" if l in "CN" else l) if binary else (lambda l: l)
    x = [f(H[i]["label"].strip().upper()) for i in ids]; y = [f(ref[i]["label"]) for i in ids]
    k, po = cohen_kappa(x, y)
    bs = []
    for _ in range(3000):
        s = [R.randrange(len(ids)) for _ in ids]
        try: bs.append(cohen_kappa([x[j] for j in s], [y[j] for j in s])[0])
        except ZeroDivisionError: pass
    bs.sort(); return k, po, bs[int(.025 * len(bs))], bs[int(.975 * len(bs)) - 1]
out = [f"Blind human labelling of {len(ids)} units (about 10% of 360)\n"]
for name, ref in (("reviewed labels (A)", A), ("LLM pre-labels", P)):
    for b, tag in ((False, "4-label"), (True, "3-label S / unsupported / X")):
        k, po, lo, hi = kap(ref, b); out.append(f"- vs {name}, {tag}: kappa = {k:.2f} (95% bootstrap CI {lo:.2f}-{hi:.2f}), raw agreement {po:.1%}")
t = "\n".join(out); (EVAL_DATA / "blind_kappa.md").write_text(t, encoding="utf-8"); print(t)
