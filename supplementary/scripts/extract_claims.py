"""Build the blinded claim-annotation sheets (read-only).

Usage:
    python eval/extract_claims.py [--b-fraction 0.35] [--seed 7]

Reads: output/<slug>/v1 (condition C1 'pipeline') and
       Paper Publication/eval_data/baseline/<slug>.json (condition C2 'baseline').
Writes to Paper Publication/eval_data/annotation/:
    records/<slug>.txt     the scraped record, one evidence line per row (give to annotators)
    annotator_A.csv        ALL items, blinded (no condition column)
    annotator_B.csv        random subset of items (for kappa)
    key.csv                item_id -> condition, slug, unit type, LLM-self-reported source,
                           and the automatic numeric check. KEEP FROM ANNOTATORS.

Annotator labels (column `label`):
    S  Supported by the record (stated, or follows directly)
    C  Contradicted by the record
    N  Not in the record (plausible but absent)
    X  Not a factual claim (slogan, question, call to action)
Column `numbers_ok`: Y/N/NA - every number, price, unit, material in the unit matches the record.
"""
from __future__ import annotations

import argparse
import csv
import random

from common import (EVAL_DATA, first_version_dirs, load_package, numbers,
                    product_records, record_lines, tokens, units)


def best_evidence(unit_text: str, lines: list[str], k: int = 2) -> str:
    ut = tokens(unit_text)
    scored = []
    for ln in lines:
        lt = tokens(ln)
        scored.append((len(ut & lt) + 2 * len(set(numbers(unit_text)) & set(numbers(ln))), ln))
    scored.sort(key=lambda x: -x[0])
    return " || ".join(l for s, l in scored[:k] if s > 0)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--b-fraction", type=float, default=0.35)
    ap.add_argument("--seed", type=int, default=7)
    a = ap.parse_args()
    rnd = random.Random(a.seed)

    ann = EVAL_DATA / "annotation"
    (ann / "records").mkdir(parents=True, exist_ok=True)
    recs = product_records()

    rows = []
    for pid, slug, d in first_version_dirs():
        rec = recs.get(pid)
        if not rec:
            continue
        lines = record_lines(rec)
        (ann / "records" / f"{slug}.txt").write_text("\n".join(lines), encoding="utf-8")
        rec_nums = set(numbers(" ".join(lines)))
        sources = [("pipeline", d)]
        bl = EVAL_DATA / "baseline" / f"{slug}.json"
        if bl.exists():
            sources.append(("baseline", bl))
        else:
            print(f"[warn] no baseline for {slug}")
        for cond, path in sources:
            for u in units(load_package(path)):
                nums = numbers(u["text"])
                missing = [n for n in nums if n not in rec_nums]
                rows.append(dict(slug=slug, condition=cond, unit_type=u["type"], text=u["text"],
                                 self_source=u["self_source"],
                                 evidence=best_evidence(u["text"], lines),
                                 auto_numbers=" ".join(nums), auto_missing=" ".join(missing)))

    # shuffle within product so condition order is not visible, then number items
    by_slug: dict[str, list] = {}
    for r in rows:
        by_slug.setdefault(r["slug"], []).append(r)
    ordered = []
    for slug in sorted(by_slug):
        rnd.shuffle(by_slug[slug])
        ordered += by_slug[slug]
    for i, r in enumerate(ordered, 1):
        r["item_id"] = f"I{i:04d}"

    key_cols = ["item_id", "slug", "condition", "unit_type", "self_source", "auto_numbers", "auto_missing"]
    with open(ann / "key.csv", "w", newline="", encoding="utf-8-sig") as f:
        w = csv.DictWriter(f, key_cols, extrasaction="ignore")
        w.writeheader(); w.writerows(ordered)

    sheet_cols = ["item_id", "product", "claim_text", "suggested_evidence", "label", "numbers_ok", "notes"]

    def write_sheet(name, items):
        with open(ann / name, "w", newline="", encoding="utf-8-sig") as f:
            w = csv.writer(f)
            w.writerow(sheet_cols)
            for r in items:
                w.writerow([r["item_id"], r["slug"], r["text"], r["evidence"], "", "", ""])

    write_sheet("annotator_A.csv", ordered)
    n_b = max(1, int(len(ordered) * a.b_fraction))
    subset = sorted(rnd.sample(ordered, n_b), key=lambda r: r["item_id"])
    write_sheet("annotator_B.csv", subset)
    print(f"{len(ordered)} items for A, {n_b} for B, "
          f"{len({r['slug'] for r in ordered})} products, "
          f"conditions: { {c: sum(1 for r in ordered if r['condition']==c) for c in ('pipeline','baseline')} }")


if __name__ == "__main__":
    main()
