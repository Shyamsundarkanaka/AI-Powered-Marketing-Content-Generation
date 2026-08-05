# AI-Powered Marketing Content Generation

Step 1: database layer and Streamlit control-center UI.
Step 2: Radboards scraper.
Step 3: background worker.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

## Seed the initial products

```bash
python -m database.seed_products
```

## Run the Streamlit app

```bash
streamlit run streamlit_app/app.py
```

## Run the background worker

```bash
python -m worker.run
```

Long-lived process; polls for queued jobs and processes them one at a time.
Queue a job from the Streamlit UI's "Queue Run" control, or leave it running
in a separate terminal alongside Streamlit. Stop with Ctrl+C.

## What's here

- `config/settings.py` — environment-driven configuration (DB path, output dir, log dir).
- `database/schema.sql` — SQLite schema: `products`, `jobs`, `versions`, `outputs`, `logs`.
- `database/connection.py` — connection handling and schema initialization.
- `database/models.py` — typed dataclasses for each table.
- `database/repository.py` — CRUD operations used by the UI and (later) the background worker.
- `database/seed_products.py` — seeds the five initial Radboards products.
- `streamlit_app/` — control center: add products, queue runs, review versions/logs. No AI inference happens here.
- `scraper/radboards.py` — scrapes one product's Shopify `.json` endpoint into structured data (title, description, price, images, specs).
- `scraper/run.py` — manual CLI: `python -m scraper.run --product-id N` or `--all`.
- `worker/run.py` — long-lived worker: `python -m worker.run` polls the `jobs` queue and runs the scraper for each job picked up.

Product lifecycle: `Pending -> Running -> Review -> Approved | Rejected | Failed | Cancelled`.
Every rejection produces a new immutable version; no version is overwritten.
