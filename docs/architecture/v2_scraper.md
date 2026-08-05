# Step 2 — Radboards Scraper

Status: **Done**. This file is a permanent record of Step 2 as shipped. It is not
edited after later steps land — new steps get their own `vN_...md` file in this
folder. See `CONTEXT.md` in this folder for the current pointer and running summary.

## 1. What this step builds

A scraper that, given a product's Radboards URL, fetches structured product
data (title, description, price, images, specs) and stores it. No background
worker exists yet, so this is invoked manually via a CLI for now; the worker
will call the same underlying function once it exists.

## 2. Key discovery: Radboards is a plain Shopify store

Every product page (e.g.
`https://radboards.in/collections/.../products/<handle>`) has a matching
**`<url>.json`** endpoint returning the full Shopify product object —
`title`, `body_html`, `variants` (with `price`/`compare_at_price`), `images`.
This is server-rendered, requires no JavaScript, and needs no HTML parsing
for the bulk of the data. This was confirmed by fetching a real product URL
and its `.json` counterpart before writing any code — decided **with the
user**, not assumed.

The only HTML parsing needed is for `body_html`, which mixes marketing copy
with a plain two-column `<table>` of specs (e.g. `Charging Time` / `120
Mins`). `scraper/radboards.py` splits these: the `<table>` rows become a
`specs` dict, and the remaining text (table removed) becomes
`description_text`.

## 3. Storage: new `scraped_data` table

One row per product, **upserted** on each scrape (not append-only history —
decided with the user, matches how `products` itself is non-versioned).

| column | notes |
|---|---|
| id | PK |
| product_id | FK -> products, cascade delete, UNIQUE (one row per product) |
| title | scraped page title |
| description_html | raw `body_html` from Shopify, unmodified |
| description_text | `body_html` with the specs `<table>` removed, then stripped to plain text |
| price / compare_at_price | REAL, from the first variant |
| image_urls | JSON array of image URLs |
| specs | JSON object, e.g. `{"Charging Time": "120 Mins", ...}` |
| scraped_at | `datetime('now')`, updated on every re-scrape |

`ScrapedData.from_row()` (in `database/models.py`) deserializes `image_urls`
and `specs` from JSON automatically.

## 4. Name drift: scraped title overwrites `products.name`

Live site content had already diverged from the original seed data (e.g. the
product seeded as **"Maverick"** — `products/maverick` — now serves a page
titled **"Roadster"**; "8.5 Off-Road Pro" now serves as "Rover Off-Roader").
**Decision (with user):** trust the scrape as source of truth — `scraper.run`
calls `update_product_name()` whenever the scraped title differs from the
DB's current name. `scraped_data.title` also independently records exactly
what was scraped, so nothing is lost either way.

## 5. What was built (file-by-file)

```
scraper/
  radboards.py    # scrape_product(url) -> dict; JSON fetch + specs/description split
  run.py          # CLI: python -m scraper.run --product-id N | --all
database/
  schema.sql       # + scraped_data table
  models.py        # + ScrapedData dataclass
  repository.py    # + upsert_scraped_data(), get_scraped_data(), update_product_name()
requirements.txt   # + requests, beautifulsoup4
```

`scraper/run.py` is a **standalone CLI**, independent of the (not-yet-built)
worker — decided with the user so the scraper is testable now. It writes to
the `logs` table (`add_log`) on both success and failure, scoped to
`product_id` with no `job_id` (no job exists yet in this flow).

## 6. How to run (from project root)

```bash
python -m scraper.run --product-id 5   # scrape one product
python -m scraper.run --all            # scrape every product in the DB
```

## 7. Verified against live data

Ran `--all` against all 7 seeded products — all 7 succeeded. Confirmed
prices, specs (5–21 image URLs per product, 6–15 spec fields), and
description text stored correctly as UTF-8 (₹, –, ×, ° characters intact;
an earlier garbled-looking terminal print was a Windows cp1252 console
display artifact, not a data problem — verified by writing to a UTF-8 file
instead).

## 8. Explicitly out of scope for Step 2

No background worker (still manual CLI invocation), no scrape-triggered job
creation, no image download/local storage (only URLs are stored), no retry/
rate-limiting logic beyond a single request per product, no scrape-history
table (upsert only, per the decision in §3).

## 9. Decisions explicitly made with the user (don't re-litigate)

- Use the Shopify `.json` endpoint, not HTML scraping — confirmed by
  inspecting a real product URL together before writing code.
- `scraped_data` is one upserted row per product, not append-only history.
- Scraped title always overwrites `products.name` on drift, no manual flag
  step.
- Scraper is invoked as a standalone CLI for now, since the worker (Step 3
  candidate) doesn't exist yet.
