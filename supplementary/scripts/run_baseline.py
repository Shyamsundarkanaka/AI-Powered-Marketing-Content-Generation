"""Run condition C2 (single-prompt baseline): ONE call per product, no retries, no validators.

Usage:  python eval/run_baseline.py [--delay 20]
Reads  Paper Publication/eval_data/baseline_prompts/<slug>.txt   (from make_baseline_prompts.py)
Writes Paper Publication/eval_data/baseline/<slug>.raw.txt       (verbatim model reply)
       Paper Publication/eval_data/baseline/<slug>.json          (only if the reply parses as JSON)
       Paper Publication/eval_data/baseline/_log.csv             (status per product)
Model comes from .env (GEMINI_MODEL) so it matches the pipeline; max output tokens default to 16000 (see --max-tokens);
temperature and every other generation setting are left at the provider default.
Existing .json files are skipped. A failed call is recorded as a failure, not retried.
"""
from __future__ import annotations

import argparse
import csv
import json
import re
import time
import urllib.error
import urllib.request

from common import EVAL_DATA, ROOT


def env() -> dict:
    d = {}
    for line in (ROOT / ".env").read_text(encoding="utf-8").splitlines():
        line = line.split("#")[0].strip() if not line.strip().startswith("#") else ""
        if "=" in line:
            k, v = line.split("=", 1)
            d[k.strip()] = v.strip().strip('"')
    return d


def call(prompt: str, model: str, key: str, max_tokens: int, timeout: int):
    url = f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent"
    body = json.dumps({"contents": [{"parts": [{"text": prompt}]}],
                       "generationConfig": {"maxOutputTokens": max_tokens}}).encode()
    req = urllib.request.Request(url, body, {"Content-Type": "application/json", "x-goog-api-key": key})
    with urllib.request.urlopen(req, timeout=timeout) as r:
        j = json.loads(r.read())
    parts = j["candidates"][0]["content"].get("parts", [])
    return "".join(p.get("text", "") for p in parts), j.get("usageMetadata", {})


def parse(text: str):
    t = text.strip()
    t = re.sub(r"^```(?:json)?\s*|\s*```$", "", t)
    return json.loads(t)


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--delay", type=int, default=20)
    ap.add_argument("--max-tokens", type=int, default=16000,
                    help="output cap incl. hidden thinking tokens; 2x the pipeline per-call cap because one call carries the whole package")
    a = ap.parse_args()
    delay = a.delay
    e = env()
    model, key = e["GEMINI_MODEL"], e["GEMINI_API_KEY"]
    max_tokens, timeout = a.max_tokens, int(e.get("LLM_TIMEOUT_SECONDS", 120))
    out = EVAL_DATA / "baseline"
    out.mkdir(parents=True, exist_ok=True)
    log_path = out / "_log.csv"
    log = list(csv.DictReader(open(log_path, encoding="utf-8"))) if log_path.exists() else []
    for pf in sorted((EVAL_DATA / "baseline_prompts").glob("*.txt")):
        slug = pf.stem
        if (out / f"{slug}.json").exists():
            continue
        status, usage, secs = "ok", {}, 0.0
        t0 = time.time()
        try:
            text, usage = call(pf.read_text(encoding="utf-8"), model, key, max_tokens, timeout)
            (out / f"{slug}.raw.txt").write_text(text, encoding="utf-8")
            try:
                (out / f"{slug}.json").write_text(json.dumps(parse(text), ensure_ascii=False, indent=2), encoding="utf-8")
            except json.JSONDecodeError as ex:
                status = f"unparseable_json: {ex}"
        except urllib.error.HTTPError as ex:
            status = f"http_{ex.code}"
        except Exception as ex:  # timeout etc.
            status = f"error: {type(ex).__name__}"
        secs = time.time() - t0
        log = [r for r in log if r["slug"] != slug] + [dict(
            slug=slug, model=model, status=status, seconds=f"{secs:.1f}",
            prompt_tokens=usage.get("promptTokenCount", ""), output_tokens=usage.get("candidatesTokenCount", ""),
            thinking_tokens=usage.get("thoughtsTokenCount", ""))]
        print(slug, status, f"{secs:.1f}s")
        with open(log_path, "w", newline="", encoding="utf-8") as f:
            w = csv.DictWriter(f, ["slug", "model", "status", "seconds", "prompt_tokens", "output_tokens", "thinking_tokens"])
            w.writeheader(); w.writerows(log)
        time.sleep(delay)


if __name__ == "__main__":
    main()
