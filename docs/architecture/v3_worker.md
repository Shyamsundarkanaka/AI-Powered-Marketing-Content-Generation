# Step 3 — Background Worker

Status: **Done**. This file is a permanent record of Step 3 as shipped. It is not
edited after later steps land — new steps get their own `vN_...md` file in this
folder. See `CONTEXT.md` in this folder for the current pointer and running summary.

## 1. What this step builds

The process that finally closes the loop between the `jobs` table (unused
until now) and real work happening: a long-lived worker that polls for
pending jobs and runs the pipeline for each, plus a UI control to queue
those jobs in the first place.

Today "the pipeline" is just the Step 2 scraper — no AI agents exist yet —
so a job currently does exactly one thing: scrape the product and store it
in `scraped_data`. Later pipeline stages (campaign brief, script, etc.)
will be added inside `worker/run.py::process_job` as they're built; this
step's job is to get the queue/worker mechanism itself working end-to-end.

## 2. Job → product status mapping (decided with the user)

| Job outcome | `jobs.status` | `products.status` |
|---|---|---|
| picked up | `Running` | `Running` |
| scrape succeeds | `Completed` | `Pending` (no generated content yet, so nothing to review — back to the front of the queue) |
| scrape fails | `Failed`, `error_message` set | `Failed` |

`Review` is intentionally not used yet — it's reserved for once a version
with actual generated content exists to review.

## 3. What was built (file-by-file)

```
worker/
  __init__.py
  run.py          # python -m worker.run — long-lived polling loop
scraper/
  run.py          # scrape_and_store() gained an optional job_id param,
                   # passed through to add_log() calls for correct log scoping
config/
  settings.py     # + WORKER_POLL_INTERVAL_SECONDS (env var, default 10s)
streamlit_app/
  app.py          # + "Queue Run" expander: pick a product, call create_job()
```

`worker/run.py` reuses `scraper.run.scrape_and_store` directly rather than
re-implementing scrape logic — the worker's job is queue management
(status transitions, logging), not scraping.

## 4. Worker behavior

- `python -m worker.run` runs forever, polling `get_next_pending_job()`
  every `WORKER_POLL_INTERVAL_SECONDS` (default 10s) when the queue is
  empty.
- Single job at a time, in creation order (oldest `Pending` job first) —
  matches the "single-worker, one-product-at-a-time" model already
  documented on `get_next_pending_job()`.
- Every job writes `logs` rows scoped to both `product_id` and `job_id`
  (start, success/failure) via the existing `add_log()`.
- Ctrl+C exits cleanly (`KeyboardInterrupt` caught, logged, no stack
  trace).

## 5. UI: queuing a job

`streamlit_app/app.py` gained a "▶️ Queue Run" expander below the products
table: a product selectbox (label shows current status) + a button that
calls `create_job(product_id)`. No per-row buttons — kept consistent with
the existing form-based "Add Product" pattern, and simpler given only ~7
products today. No duplicate-job guard: queuing a product that already has
a pending/running job is harmless (processed in order), and re-queuing an
idle product on demand (re-scrape) is a legitimate use case.

## 6. How to run (from project root, two terminals)

```bash
# terminal 1
python -m worker.run

# terminal 2
streamlit run streamlit_app/app.py
# -> expand "Queue Run", pick a product, click "Queue Run"
```

## 7. Explicitly out of scope for Step 3

- **Crash recovery**: if the worker is killed mid-job, that job and its
  product are left stuck in `Running` with no automatic reset. Revisit
  when logging/monitoring (roadmap item 6) is picked up.
- **Concurrency**: still strictly one job at a time, matching the existing
  single-worker model — no parallel workers, no locking beyond that.
- **Any pipeline stage beyond scraping** — `process_job` will grow as
  LangGraph/AI agents, TTS, and rendering land.

## 8. Decisions explicitly made with the user (don't re-litigate)

- Worker is a long-lived polling loop (`python -m worker.run`), not a
  one-shot cron-triggered script.
- A job today = scrape only; success returns the product to `Pending`
  (not `Review`), since there's nothing generated to review yet.
- Job queuing happens via a Streamlit UI control (`create_job()` call),
  not a separate CLI.
