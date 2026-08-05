# Project Context — start here in a new chat

**Load this file first.** It tells you what's done, what's next, and which
versioned doc in this folder has the full detail — so you don't need to
re-read the whole repo or re-derive decisions already made.

## What this project is

AI-powered marketing content generator for Radboards products: given a
product name + URL, scrape it, generate a campaign brief / script / caption
/ hashtags / voiceover / video plan / rendered video, and route each
generated version through a human review (approve/reject) loop. SQLite is
the single source of truth. Streamlit is the control-center UI only — it
never runs AI inference itself; a separate background worker does.

## Where things stand

**Step 1 done: database layer + Streamlit control-center UI shell.**
**Step 2 done: Radboards scraper.**
**Step 3 done: background worker.**
Full detail, schema, file list, decisions made, and rationale:
→ **[`v1_step1_database_streamlit.md`](./v1_step1_database_streamlit.md)**
→ **[`v2_scraper.md`](./v2_scraper.md)**
→ **[`v3_worker.md`](./v3_worker.md)**

In short: 5-table SQLite schema (`products`, `jobs`, `versions`, `outputs`,
`logs`) with CRUD in `database/repository.py`; a Streamlit app
(`streamlit_app/app.py`) whose main tab is a filterable/searchable Products
table with an inline add-product form; and an Output tab
(`streamlit_app/pages/1_Output.py`) showing versions/artifacts per product
(currently empty — no worker exists yet to populate it). Seeded with 5
Radboards products + 2 added manually during testing (7 total).

`scraper/radboards.py` scrapes a product's Shopify `.json` endpoint (title,
description, price, images, specs) and upserts one row per product into the
`scraped_data` table; still runnable manually via `python -m scraper.run --all`
or `--product-id N`. All 7 seeded products have been scraped; product names
were updated to match live site titles where they'd drifted (e.g. "Maverick"
-> "Roadster").

`worker/run.py` (`python -m worker.run`) is a long-lived process that polls
`get_next_pending_job()` and runs the scraper for whatever job it picks up,
updating job/product status and writing log lines — the Streamlit "Queue Run"
control (in `streamlit_app/app.py`) calls `create_job()` to add work to that
queue. A job today only scrapes (no AI agents exist yet); on success the
product returns to `Pending`, on failure it becomes `Failed`. The Output tab
still shows nothing new yet, since no version/output rows are created until
content-generation stages exist.

## What's NOT built yet (next steps, no invented specifics)

These are listed as a roadmap only — deliberately not designed in detail
until we actually get there, so nothing here is a commitment to a specific
implementation:

1. **LangGraph workflow + AI agents** — campaign brief, script, caption,
   hashtags generation, using `scraped_data` as input. Streamlit must stay
   out of this entirely. This is the thing that will finally make the
   Output tab show real data (versions/outputs), since `process_job` in
   `worker/run.py` currently only scrapes.
2. **Voiceover (TTS)** generation.
3. **Video plan + rendering** (likely moviepy, per earlier scaffolding that
   was intentionally not restored — see "Notes" below).
4. **Reviewer-feedback-as-context loop**: when a version is rejected, its
   `reviewer_feedback` needs to actually be fed into the next generation
   attempt for that product.
5. **Logging/monitoring, error handling, testing strategy** — not yet
   revisited since Step 1's minimal logging table. Also includes: worker
   crash recovery (a killed worker leaves job/product stuck in `Running`).

Pick these up one at a time, in roughly this order, unless told otherwise.

## Conventions to keep following

- New step → new file in this folder: `v2_<short-name>.md`, `v3_...`, etc.
  Never edit a past `vN` file after the fact — it's a record of what shipped
  at that point. Update *this* CONTEXT.md's "Where things stand" /
  "next steps" sections instead, and add the new file to the list below.
- Run everything from the project root (`pip install -r requirements.txt`,
  `python -m database.seed_products`, `streamlit run streamlit_app/app.py`).
- All config via env vars (`config/settings.py`), paths anchored to
  `BASE_DIR` — never assume the process cwd.
- SQLite is the only persistence layer; don't introduce another one.
- Streamlit must never call an AI model directly.

## Notes on prior repo state

An earlier, unrelated scaffold (agents/, scraper/, database/ with different
contents, tests/, etc., committed as "Chatgpt CHanges") was found **deleted
from disk but still in git history** at the start of this work. Per explicit
user decision, it was **not restored** — everything under `database/` and
`streamlit_app/` described here was built fresh. If you ever see references
to that old scaffold's file layout, they don't apply to the current code.

## Version index

| File | Step | Status |
|---|---|---|
| [`v1_step1_database_streamlit.md`](./v1_step1_database_streamlit.md) | Step 1 — Database + Streamlit UI | Done |
| [`v2_scraper.md`](./v2_scraper.md) | Step 2 — Radboards scraper | Done |
| [`v3_worker.md`](./v3_worker.md) | Step 3 — Background worker | Done |
