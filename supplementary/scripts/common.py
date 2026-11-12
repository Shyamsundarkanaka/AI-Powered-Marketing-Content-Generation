"""Shared read-only helpers for the offline evaluation scripts.

These scripts only READ data/app.db, brand/brand.yaml and output/. They never
import or modify the application. Standard library only.
"""
from __future__ import annotations

import json
import re
import sqlite3
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
DB = ROOT / "data" / "app.db"
OUTPUT = ROOT / "output"
BRAND = ROOT / "brand" / "brand.yaml"
EVAL_DATA = ROOT / "Paper Publication" / "eval_data"


def db():
    return sqlite3.connect(f"file:{DB.as_posix()}?mode=ro", uri=True)


def product_records() -> dict[int, dict]:
    """product_id -> scraped record (latest scrape)."""
    out = {}
    with db() as c:
        for pid, title, desc, price, cmp_, specs in c.execute(
            "select product_id,title,description_text,price,compare_at_price,specs "
            "from scraped_data order by id"
        ):
            try:
                specs = json.loads(specs) if specs else {}
            except json.JSONDecodeError:
                specs = {}
            out[pid] = dict(title=title, description=desc or "", price=price,
                            compare_at=cmp_, specs=specs)
    return out


def record_lines(rec: dict) -> list[str]:
    """The scraped record as atomic evidence lines."""
    lines = [f"Title: {rec['title']}"]
    if rec["price"] is not None:
        lines.append(f"Price: {fmt_money(rec['price'])}")
    if rec["compare_at"]:
        lines.append(f"Compare-at price: {fmt_money(rec['compare_at'])}")
    for k, v in rec["specs"].items():
        lines.append(f"Spec - {k}: {v}")
    for s in split_sentences(rec["description"]):
        lines.append(f"Description: {s}")
    return lines


def fmt_money(x) -> str:
    try:
        return f"₹{float(x):,.0f}"
    except (TypeError, ValueError):
        return str(x)


def split_sentences(text: str) -> list[str]:
    parts = re.split(r"(?<=[.!?])\s+|\n+", text or "")
    return [p.strip() for p in parts if p and p.strip()]


def first_version_dirs() -> list[tuple[int, str, Path]]:
    """(product_id, slug, dir of version 1) for every product with output.

    Version 1 is never a reviewer-driven revision, so it is the clean
    first-generation output used as condition C1.
    """
    res = []
    with db() as c:
        for pid, odir in c.execute(
            "select product_id, output_dir from versions where version_number=1 order by product_id"
        ):
            p = Path(odir)
            if not p.exists():  # path recorded on another machine
                p = OUTPUT / p.parent.name / p.name
            if (p / "script.json").exists():
                res.append((pid, p.parent.name, p))
    return res


def load_package(d: Path) -> dict:
    """Pull the claim-bearing text out of one output folder (or baseline json)."""
    pkg = {}
    if d.suffix == ".json":
        j = json.loads(d.read_text(encoding="utf-8"))
        pkg["brief"] = j.get("campaign_brief", {})
        pkg["script"] = j.get("script", {})
        pkg["caption"] = j.get("caption", "")
        h = j.get("hashtags", "")
        pkg["hashtags"] = " ".join(h) if isinstance(h, list) else str(h)
        return pkg
    pkg["brief"] = json.loads((d / "campaign_brief.json").read_text(encoding="utf-8"))
    pkg["script"] = json.loads((d / "script.json").read_text(encoding="utf-8"))
    pkg["caption"] = (d / "caption.txt").read_text(encoding="utf-8")
    hp = d / "hashtags.txt"
    pkg["hashtags"] = hp.read_text(encoding="utf-8") if hp.exists() else ""
    return pkg


def units(pkg: dict) -> list[dict]:
    """Split a package into annotatable units (one sentence / proof point each)."""
    out = []
    for pp in pkg["brief"].get("proof_points", []) or []:
        if isinstance(pp, dict):
            out.append(dict(type="proof_point", text=pp.get("claim", ""),
                            self_source=pp.get("source", "")))
        else:
            out.append(dict(type="proof_point", text=str(pp), self_source=""))
    for b in pkg["script"].get("beats", []) or []:
        for s in split_sentences(b.get("line", "")):
            out.append(dict(type="script:" + b.get("beat", ""), text=s, self_source=""))
    cap = re.sub(r"(?:^|\s)#\w+", "", pkg["caption"])
    for s in split_sentences(cap):
        out.append(dict(type="caption", text=s, self_source=""))
    return [u for u in out if u["text"].strip()]


NUM = re.compile(r"\d[\d,]*\.?\d*")


def numbers(text: str) -> list[str]:
    return [n.replace(",", "").rstrip(".") for n in NUM.findall(text)]


def tokens(text: str) -> set[str]:
    return {t for t in re.findall(r"[a-z0-9]+", text.lower()) if len(t) > 2 or t.isdigit()}
