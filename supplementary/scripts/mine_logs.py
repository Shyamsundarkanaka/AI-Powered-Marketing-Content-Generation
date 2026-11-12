"""Success rate, latency and shape-retry statistics from data/app.db and logs/app.log (read-only).

Usage:  python eval/mine_logs.py [--since "2026-11-12 00:00:00"]
Writes Paper Publication/eval_data/pipeline_stats.md and prints it.
"""
from __future__ import annotations

import argparse
import re
import statistics as st
from collections import Counter, defaultdict
from datetime import datetime

from common import EVAL_DATA, ROOT, db

FMT = "%Y-%m-%d %H:%M:%S"
STAGE = re.compile(r"^(campaign_brief|script|caption|hashtags|video_plan): (?:generated|needed (\d) attempts)")


def q(xs, p):
    xs = sorted(xs)
    if not xs:
        return float("nan")
    k = (len(xs) - 1) * p
    f = int(k); c = min(f + 1, len(xs) - 1)
    return xs[f] + (xs[c] - xs[f]) * (k - f)


def summ(xs):
    return f"median {st.median(xs):.1f} (IQR {q(xs,.25):.1f}-{q(xs,.75):.1f}), n={len(xs)}" if xs else "n=0"


def classify(msg: str) -> str:
    m = (msg or "").lower()
    if m.startswith("[scrape]"):
        return "infrastructure: store scrape (HTTP 429 rate limit / 404 stale URL)"
    if "503" in m or "unavailable" in m:
        return "infrastructure: provider 503 overloaded"
    if "resource_exhausted" in m or "quota" in m or "429" in m:
        return "infrastructure: quota/rate limit"
    if "429" in m or "quota" in m or "resource_exhausted" in m or "rate" in m:
        return "infrastructure: quota/rate limit"
    if "404" in m or "not found" in m:
        return "infrastructure: model not found"
    if "timeout" in m or "timed out" in m:
        return "infrastructure: timeout"
    if "attempt" in m or "validation" in m or "unusable" in m or "chars" in m:
        return "validation exhaustion"
    return "other"


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--since", default="1970-01-01 00:00:00")
    since = ap.parse_args().since
    out = []
    with db() as c:
        jobs = c.execute("select id,product_id,status,error_message,started_at,completed_at from jobs "
                         "where started_at>=? order by id", (since,)).fetchall()
        logs = c.execute("select job_id,message,created_at from logs where created_at>=? order by id",
                         (since,)).fetchall()

    n = len(jobs)
    ok = [j for j in jobs if j[2] == "Completed"]
    out.append(f"## Job outcomes (since {since})\n")
    out.append(f"- jobs: {n}; completed: {len(ok)} ({100*len(ok)/max(n,1):.0f}%)")
    fails = Counter(classify(j[3]) for j in jobs if j[2] != "Completed")
    for k, v in fails.items():
        out.append(f"- failed - {k}: {v}")
    dur = [(datetime.strptime(j[5], FMT) - datetime.strptime(j[4], FMT)).total_seconds()
           for j in ok if j[4] and j[5]]
    out.append(f"- end-to-end seconds (completed jobs): {summ(dur)}")

    # stage completion offsets relative to 'Pipeline started'
    starts, stage_t = {}, defaultdict(lambda: defaultdict(list))
    attempts = defaultdict(dict)
    tts, vid = [], []
    for job, msg, ts in logs:
        t = datetime.strptime(ts, FMT)
        if msg.startswith("Pipeline started"):
            starts[job] = t
        elif job in starts:
            m = STAGE.match(msg)
            if m:
                stage_t[m.group(1)][job] = (t - starts[job]).total_seconds()
                attempts[m.group(1)][job] = int(m.group(2) or 1)
            elif msg.startswith("voiceover:"):
                stage_t["voiceover"][job] = (t - starts[job]).total_seconds()
                x = re.search(r"([\d.]+)s", msg)
                if x: tts.append(float(x.group(1)))
            elif msg.startswith("video:"):
                stage_t["video_done"][job] = (t - starts[job]).total_seconds()
                x = re.search(r"([\d.]+)s", msg)
                if x: vid.append(float(x.group(1)))
    out.append("\n## Stage completion time after pipeline start (seconds)\n")
    out.append("| stage | summary |\n|---|---|")
    for s in ("campaign_brief", "script", "hashtags", "caption", "video_plan", "voiceover", "video_done"):
        out.append(f"| {s} | {summ(list(stage_t[s].values()))} |")
    out.append(f"\n- generated voiceover length (s): {summ(tts)}; video length (s): {summ(vid)}")

    # validation retries, from the per-job "X: needed N attempts" rows in the logs table
    out.append("\n## Validation retries per LLM node (jobs that reached that node)\n")
    exhausted = Counter()
    for j in jobs:
        m = re.match(r"\[(\w+)\].*did not return a usable response", j[3] or "")
        if m:
            exhausted[m.group(1)] += 1
    out.append("| node | first-attempt OK | needed 2 attempts | needed 3 attempts | exhausted 3/3 (job failed) | executions |\n|---|---|---|---|---|---|")
    for node in ("campaign_brief", "script", "hashtags", "caption", "video_plan"):
        a = Counter(attempts[node].values())
        out.append(f"| {node} | {a[1]} | {a[2]} | {a[3]} | {exhausted[node]} | {sum(a.values()) + exhausted[node]} |")
    with db() as c2:
        rs = [m for (m,) in c2.execute("select message from logs where message like 'script: needed%'")]
    out.append(f"\n- script retries logged: {len(rs)}; 'beats must contain exactly 5 entries' = {sum('must contain exactly' in m for m in rs)}, spoken-length window = {sum('seconds when spoken' in m for m in rs)}")

    text = "\n".join(out)
    EVAL_DATA.mkdir(parents=True, exist_ok=True)
    (EVAL_DATA / "pipeline_stats.md").write_text(text, encoding="utf-8")
    print(text)


if __name__ == "__main__":
    main()
