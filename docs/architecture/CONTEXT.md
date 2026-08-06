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
**Step 4 done: brand system, LangGraph pipeline, voiceover, video rendering,
reviewer-feedback loop.**
Full detail, schema, file list, decisions made, and rationale:
→ **[`v1_step1_database_streamlit.md`](./v1_step1_database_streamlit.md)**
→ **[`v2_scraper.md`](./v2_scraper.md)**
→ **[`v3_worker.md`](./v3_worker.md)**
→ **[`v4_langgraph_pipeline.md`](./v4_langgraph_pipeline.md)**

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
`get_next_pending_job()` and, for each job, scrapes the product and then runs
the LangGraph pipeline over the scraped data. The Streamlit "Queue Run" control
(in `streamlit_app/app.py`) calls `create_job()` to add work to that queue.

A job now produces a complete reviewable version — campaign brief, script,
caption, hashtags, voiceover WAV, video plan and a rendered 1080x1920 MP4 —
under `output/<product>/v<N>/`, and leaves the product in `Review`. The Output
tab renders those artifacts inline (video/audio players, markdown, copyable
caption) with Approve / Reject-and-regenerate controls.

`ANTHROPIC_API_KEY` defaults to a **placeholder**, so out of the box every agent
call 401s and each node falls back to its documented stub output — realistic
copy built from the product's real scraped data, marked `STUB` in the UI and in
`_meta.json`. Drop a real key into `.env` and it generates for real with no code
change. The video and voiceover are real artifacts either way.

Rejecting a version requires typed feedback, auto-queues a regeneration job, and
that feedback plus the previous copy is injected into every agent prompt for the
next version.

## What's NOT built yet (next steps, no invented specifics)

Roadmap items 1-4 (LangGraph agents, voiceover, video, feedback loop) all
landed in Step 4. What remains, deliberately not designed in detail until we
get there:

1. **Testing strategy** — there is still no automated test anywhere. Every
   check in Steps 1-4 was manual. This is now the largest gap by some margin.
2. **Real TTS** — voiceover is silence of the correct duration by default;
   `ENABLE_TTS=true` with `pyttsx3` is a stopgap, not a provider integration.
3. **Worker crash recovery** — a killed worker still leaves a job and product
   stuck in `Running`. (Step 4 fixed the related orphan-*version* problem: the
   `versions` row is now created at the end of a run, not the start.)
4. **Programmatic brand enforcement** — the banned vocabulary and compliance
   rules are injected into prompts and documented in `brand/COMPLIANCE.md`, but
   nothing in code rejects a violating generation. The human reviewer is the
   only backstop.
5. **Monitoring** — logging is still just the `logs` table plus stdout.

Pick these up one at a time, in roughly this order, unless told otherwise.

## Conventions to keep following

- New step → new file in this folder: `v2_<short-name>.md`, `v3_...`, etc.
  Never edit a past `vN` file after the fact — it's a record of what shipped
  at that point. Update *this* CONTEXT.md's "Where things stand" /
  "next steps" sections instead, and add the new file to the list below.
- Run everything from the project root (`pip install -r requirements.txt`,
  `python -m database.seed_products`, `streamlit run streamlit_app/app.py`).
- Brand rules live in `brand/brand.yaml`, not in Python. Agents read it via
  `graph/prompts.py`; the renderer reads it via `media/movie.py`. Never
  hard-code a colour, a persona or a content rule.
- Agents may only state facts present in `scraped_data` — that constraint is the
  reason they are given nothing else about the product.
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
| [`v4_langgraph_pipeline.md`](./v4_langgraph_pipeline.md) | Step 4 — Brand system, LangGraph pipeline, voiceover, video | Done |
