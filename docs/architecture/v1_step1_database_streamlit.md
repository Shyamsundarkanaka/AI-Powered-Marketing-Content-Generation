# Step 1 — Database Layer & Streamlit Control Center

Status: **Done**. This file is a permanent record of Step 1 as shipped. It is not
edited after later steps land — new steps get their own `vN_...md` file in this
folder. See `CONTEXT.md` in this folder for the current pointer and running summary.

## 1. Purpose of the system

An AI-powered marketing content generation system for Radboards (hoverboard
e-commerce) products. Given a product name + URL, the system will eventually:
scrape the product page, generate a campaign brief, script, caption, hashtags,
voiceover, video plan, and a rendered video — then let a human reviewer
approve or reject each generated version. Rejections feed back as context for
a re-run; nothing generated is ever overwritten.

Step 1 builds only the **data model** and the **control-center UI shell**
around that lifecycle — no scraping, no AI calls, no rendering yet.

## 2. Core architectural rules (apply to every future step)

- **SQLite is the single source of truth** for products, jobs, versions,
  outputs and logs. No other persistence layer.
- **Streamlit never performs AI inference.** It only reads/writes the
  database and displays state. All reasoning/generation work happens in a
  separate background worker (not built yet).
- **One product processed at a time** (single-worker model, not built yet).
- **Versions are immutable.** A rejection creates a new version row; no row
  is ever updated/overwritten to represent a new generation attempt.
- **All configuration lives in environment variables** (`.env`, see
  `.env.example`), loaded once in `config/settings.py`.
- Paths in config are resolved **relative to the project root
  (`BASE_DIR`)**, never to the process's current working directory — see
  §5 "Bug fixed" for why this matters.

## 3. Product lifecycle (state machine)

```
Pending -> Running -> Review -> Approved
                    -> Rejected -> (new version created) -> Running -> Review -> ...
        -> Failed
        -> Cancelled
```

These 7 states are the actual `products.status` values used in the UI and DB
today. (We considered collapsing them into a simpler 4-state display
vocabulary — Pending/Processing/Feedback Awaiting/Completed — but decided
**against** it: the UI shows all 7 real states as-is.)

## 4. Database schema (`database/schema.sql`)

SQLite file lives at `<project_root>/data/app.db` (created automatically on
first run via `init_db()`).

### `products`
| column | type | notes |
|---|---|---|
| id | INTEGER PK | |
| name | TEXT | |
| url | TEXT UNIQUE | one row per source URL |
| status | TEXT | CHECK'd against the 7 lifecycle states, default `Pending` |
| output_dir | TEXT | `<OUTPUT_DIR>/<slugified-name>` |
| created_at / updated_at | TEXT | `datetime('now')` |

### `jobs`
| column | notes |
|---|---|
| id | PK |
| product_id | FK -> products, cascade delete |
| status | `Pending / Running / Completed / Failed / Cancelled` |
| error_message, created_at, started_at, completed_at | |

One row per "Run" click. The (not-yet-built) worker will poll for the oldest
`Pending` job via `get_next_pending_job()`.

### `versions`
| column | notes |
|---|---|
| id | PK |
| product_id | FK -> products |
| job_id | FK -> jobs, nullable |
| version_number | auto-incremented per product, starting at 1 |
| status | `Review / Approved / Rejected` |
| reviewer_feedback | TEXT, set on reject |
| output_dir | `<product.output_dir>/v<N>` |
| created_at | |

Never updated to represent new content — only `status`/`reviewer_feedback`
change (approve/reject), and only a fresh row represents a new generation.

### `outputs`
One row per artifact belonging to a version: `output_type` is one of
`campaign_brief / script / caption / hashtags / voiceover / video_plan /
video`, plus `file_path`.

### `logs`
Free-form `product_id` / `job_id` scoped log lines (`level`, `message`,
`created_at`) for future worker/pipeline diagnostics.

All CRUD lives in `database/repository.py` (no raw SQL anywhere else).
Typed dataclasses mirroring each table are in `database/models.py`.

## 5. Bug fixed: DB path resolved against cwd, not project root

**Symptom:** products added through the Streamlit UI didn't show up next to
the 5 seeded products.

**Root cause:** `config/settings.py` originally did
`Path(os.getenv("DATABASE_PATH", "./data/app.db")).resolve()` — a relative
path resolved against whatever directory the process happened to be launched
from. Running the seed script from the project root and launching Streamlit
from a different working directory (e.g. `streamlit_app/`) silently created
**two different SQLite files** (`./data/app.db` and
`./streamlit_app/data/app.db`).

**Fix:** `_resolve()` in `config/settings.py` now anchors any relative path
to `BASE_DIR` (the project root, derived from `settings.py`'s own location),
regardless of process cwd. The stray `streamlit_app/data/app.db` was merged
into `./data/app.db` and deleted. **Always run commands from the project
root** (`python -m database.seed_products`, `streamlit run
streamlit_app/app.py`) — it no longer matters for correctness, but it's the
convention used throughout this doc.

## 6. What was actually built (file-by-file)

```
config/
  settings.py          # env-driven config; BASE_DIR-anchored paths (see §5)
database/
  schema.sql            # DDL for the 5 tables above
  connection.py          # get_connection(), connection_scope() ctx-manager, init_db()
  models.py              # Product / Job / Version / Output / LogEntry dataclasses
  repository.py           # all CRUD, incl. count_rejections_by_product()/_for_product()
  seed_products.py        # seeds the 5 initial Radboards products (idempotent)
streamlit_app/
  app.py                  # MAIN TAB: Products table (see §7)
  pages/
    1_Output.py            # OUTPUT TAB: versions/outputs viewer (see §8)
.env.example, .gitignore, README.md, requirements.txt
```

Note: `streamlit_app/pages/1_Add_Product.py` and
`streamlit_app/pages/2_Product_Dashboard.py` were built in an earlier pass
and then **deleted** — Add Product became an inline form on the main tab,
and Product Dashboard was replaced by the Output tab (see §7, §8).

## 7. Main tab (`streamlit_app/app.py`)

- Inline **"➕ Add Product"** expander (form: name + URL only). No separate
  page for this.
- Status-count metric row across all 7 lifecycle states.
- **Products table** — the centerpiece of the app:
  - Columns: `ID, Name, URL (clickable link), Status, Last Updated,
    Rejections, View Output (clickable link)`.
  - `Rejections` = count of that product's `versions` rows with
    `status = 'Rejected'` (via `count_rejections_by_product()`, one query for
    the whole table).
  - `View Output` link points to `Output?product_id=<id>` — a same-app
    relative URL Streamlit resolves to the `1_Output.py` page, pre-selecting
    that product via `st.query_params`.
  - **Filters:** multiselect over the 7 statuses, plus a free-text search box
    matched case-insensitively against name and URL. Both applied in Python
    before rendering (no DB-level filtering needed at this scale).

## 8. Output tab (`streamlit_app/pages/1_Output.py`)

Replaces the old "Product Dashboard" page. Reachable either via the nav
sidebar or via a row's `View Output` link (which pre-selects that product).

- Product picker (defaults to whichever product the link specified).
- Product summary (name, URL, status, output dir).
- **Latest version shown first, expanded by default**; all earlier versions
  listed below, collapsed.
- Each version panel shows its output directory, reviewer feedback (if
  rejected), a table of recorded `outputs` rows, and — if the version is
  still `Review` — Approve/Reject controls (reject requires typed feedback,
  which is stored on the version row and flips the product back to
  `Rejected`).
- Currently shows **"No versions yet"** for every product, because no
  worker exists yet to create version rows. This is expected, not a bug.

## 9. Seed data

`python -m database.seed_products` (run once already) inserted these 5
products, all currently `Pending`:

1. 8.5 Off-Road Pro
2. Classic 6.5 Limited Edition
3. Classic 6.5 Lightning Edition
4. Rover Off-Roader XL
5. Maverick

Plus 2 more added manually through the UI during testing (electric unicycle
Kingsong 14D and S16) — all 7 currently live in `data/app.db`.

Script is idempotent — re-running skips any URL already present
(`sqlite3.IntegrityError` on the `UNIQUE` constraint, caught and reported).

## 10. How to run (from project root)

```bash
pip install -r requirements.txt
copy .env.example .env            # optional, defaults work as-is
python -m database.seed_products   # only needed once / to add the seed set
streamlit run streamlit_app/app.py
```

## 11. Explicitly out of scope for Step 1

No scraping, no LangGraph, no AI agents (campaign brief / script / caption /
hashtags / voice), no TTS, no video rendering, no background worker process.
Jobs can be *created* (Run button) but nothing ever consumes them yet —
there is no process that flips a job to `Running`/`Completed` or creates a
`version` row. That is Step 2+.

## 12. Decisions explicitly made with the user (don't re-litigate)

- Keep all 7 internal product states visible in the UI as-is — no simplified
  4-state display vocabulary.
- Add Product is inline on the main tab, not a separate page.
- Product Dashboard page removed; Output tab takes over its "versions/logs
  for one product" role, reached via the table's View Output link.
- Config paths must be anchored to project root, not cwd — this was a real
  bug that caused data to silently split across two DB files.
