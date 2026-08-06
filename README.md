# AI-Powered Marketing Content Generation

Give it a Radboards product URL. It scrapes the product, runs a LangGraph
pipeline of Claude agents over the scraped facts, and produces a complete,
reviewable content version — campaign brief, script, caption, hashtags,
voiceover and a rendered 1080×1920 vertical video — then routes it through a
human approve/reject loop where a rejection regenerates with your feedback.

- Step 1: database layer and Streamlit control-center UI
- Step 2: Radboards scraper
- Step 3: background worker
- Step 4: brand system, LangGraph pipeline, voiceover, video rendering, feedback loop

Full architecture and decisions: [`docs/architecture/CONTEXT.md`](docs/architecture/CONTEXT.md).

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

No system ffmpeg needed — `imageio-ffmpeg` bundles its own binary.

### The API key

`ANTHROPIC_API_KEY` defaults to a **placeholder**, and that is a supported way to
run the system. Every agent call is attempted, returns 401, and each node falls
back to its documented stub output: realistic, brand-correct copy built from the
product's *real* scraped data. The pipeline still completes, and the voiceover
and video are real rendered artifacts either way.

The Output tab shows stub content exactly as it would show a real generation —
no badge, no warning — so the app is reviewable end to end before you ever set
a real key. Provenance (`"_source": "stub"`, plus a `WARNING` in the `logs`
table) is still recorded internally for debugging, just not surfaced to the
reviewer. Put a real key in `.env` to generate for real; no code changes
anywhere.

## Run it

```bash
python -m database.seed_products      # once, seeds the initial products
streamlit run streamlit_app/app.py    # one terminal — starts the worker too
```

The Streamlit app starts the worker loop itself, on a background thread, the
first time any page loads — one command runs the whole thing, and a job can
never get stuck `Pending` because nothing was around to process it. (For a
production-shaped deployment, run `python -m worker.run` as its own
long-lived process instead — see its docstring.)

Then in the UI: **Run** on a product → the worker scrapes it and generates a
version → **Review** to watch the video, read the copy, and approve or
reject. Rejecting requires feedback and automatically queues a regeneration
that takes your feedback into account.

### Without the UI

```bash
python -m scraper.run --product-id 5      # scrape one product (or --all)
python -m graph.pipeline 5                # generate a full version for it
python -m media.movie --product-id 5      # render just the video, standalone
python -m media.voice --seconds 28        # generate just a voiceover track
```

## What's here

**Pipeline**
- `graph/pipeline.py` — graph topology and `run_pipeline()`. Brief → script →
  (caption ∥ hashtags ∥ video plan) → voiceover → video → finalize.
- `graph/nodes.py` — the nine node functions.
- `graph/prompts.py` — per-agent prompts, with the brand definition injected into
  every one. Agents may only state facts present in the scraped data.
- `graph/llm.py` — the single place we call Claude, and the single place we fall
  back to a stub.
- `graph/stubs.py` — the documented fallback output for each node.
- `graph/state.py` — pipeline state and the reducers that make the fan-out safe.

**Brand** — `brand/`
- `brand.yaml` is the machine-readable source of truth: voice, banned
  vocabulary, personas, language rules, per-artifact content rules, compliance
  guardrails, palette, typography, safe areas, motion.
- It has two consumers: every agent prompt, and the video renderer. Changing a
  hex value or a content rule there changes the output with no code edit.
- `BRAND_GUIDELINES.md`, `PERSONAS.md`, `VISUAL_IDENTITY.md`, `COMPLIANCE.md`
  carry the reasoning behind it.

**Media**
- `media/movie.py` — the renderer. 1080×1920 vertical (square/landscape also
  supported), Ken Burns with eased camera moves, white-backdrop cutout so the
  product floats rather than sitting in a pasted rectangle, branded type with
  drop shadows and spec pills, cross-dissolves, progress bar, H.264/AAC out.
- `media/voice.py` — voiceover. No TTS provider is wired up, so the default is
  silence of exactly the script's estimated spoken length: video timing is
  already correct and a real narration WAV of the same length drops straight in.

**Everything else**
- `config/settings.py` — environment-driven config; paths anchored to the
  project root, not the cwd.
- `database/` — SQLite schema, typed models, and all CRUD. Source of truth for
  products, jobs, versions, outputs, scraped data and logs.
- `scraper/radboards.py` — scrapes a product's Shopify `.json` endpoint.
- `worker/run.py` — polls the job queue; each job scrapes then runs the pipeline.
- `streamlit_app/` — control center. Never calls a model.

## How it hangs together

- **SQLite is the only source of truth.** No second persistence layer.
- **Streamlit never performs inference.** It reads and writes the database and
  renders files. All generation happens in the worker process.
- **One product at a time**, single worker, jobs processed in creation order.
- **Versions are immutable.** A rejection never overwrites — it creates a new
  version, and the reviewer's feedback plus the previous copy are injected into
  every agent prompt for that next attempt.
- **Agents may only use scraped facts.** They are handed the `scraped_data` row
  and nothing else about the product, so an invented spec has nowhere to come
  from.

Product lifecycle: `Pending → Running → Review → Approved | Rejected | Failed | Cancelled`.
