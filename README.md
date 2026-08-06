# AI-Powered Marketing Content Generation

Give it a Shopify product URL. It scrapes the product, runs a LangGraph pipeline
of agents over the scraped facts, and produces a complete, reviewable content
version — campaign brief, script, caption, hashtags, voiceover and a rendered
1080×1920 vertical video — then routes it through a human approve/reject loop
where a rejection regenerates with your feedback.

**Nothing in the output is fabricated locally.** Every piece of copy is real
model output that passed schema validation, or the run fails and tells you why.
There is no placeholder mode, no canned fallback copy, and no way for a reviewer
to be shown sample text believing it was generated.

## Setup

```bash
python -m venv venv
venv\Scripts\activate
pip install -r requirements.txt
copy .env.example .env
```

No system ffmpeg needed — `imageio-ffmpeg` bundles its own binary.

### Configure a model

Put a real API key in `.env` for whichever provider you select:

```ini
LLM_PROVIDER=gemini
GEMINI_API_KEY=your-real-key
```

`openai` and `anthropic` are equally supported — set `LLM_PROVIDER` and fill in
that block instead. Switching provider or model is a `.env` change only; see
[`docs/architecture/llm-providers.md`](docs/architecture/llm-providers.md).

Without a valid key the Dashboard shows a red banner and every run fails
immediately with a clear message, rather than silently producing filler.

## Run it

```bash
python -m database.seed_products      # once, seeds the starting products
streamlit run streamlit_app/app.py    # one terminal — starts the worker too
```

The Streamlit app starts the worker loop itself, on a background thread, the
first time any page loads — one command runs the whole thing, and a job can
never get stuck `Pending` because nothing was around to process it. For a
production deployment, run `python -m worker.run` as its own long-lived process
instead (see its docstring).

Then in the UI: **Run** on a product → the worker scrapes it and generates a
version → **Review** to watch the video, read the copy, and approve or reject.
Rejecting requires feedback and queues a regeneration that takes it into
account. You can scope the feedback to specific parts (caption, hashtags, …) —
anything outside the scope is carried forward unchanged instead of being
regenerated and re-billed.

### Without the UI

```bash
python -m scraper.run --product-id 1              # scrape one product (or --all)
python -m graph.pipeline 1                        # generate a full version for it
python -m media.movie --plan output/…/v1/video_plan.json   # re-render just the video
python -m media.voice --text "hello there"        # test the TTS chain
python -m database.reset                          # wipe everything, re-seed
pytest                                            # run the test suite
```

## What's here

**Pipeline** — `graph/`
- `pipeline.py` — graph topology and `run_pipeline()`. Brief → script →
  (caption ∥ hashtags ∥ video plan) → voiceover → video → finalize.
- `nodes.py` — the nine node functions, plus feedback scoping and carry-forward.
- `prompts.py` — per-agent prompts, with the brand definition injected into every
  one. Agents may only state facts present in the scraped data.
- `schemas.py` — validates and normalizes every model response. Fixable problems
  are corrected locally; the rest are sent back to the model with the reason.
- `llm.py` — the one place the system talks to a model, and the one place it
  gives up. Provider registry, hardened JSON extraction, repair-retry.
- `state.py` — pipeline state and the reducers that make the fan-out safe.

**Brand** — `brand/`
- `brand.yaml` — machine-readable source of truth: voice, personas, content
  rules, compliance, palette, typography, video geometry. Every agent prompt and
  every rendered frame is built from it.
- `loader.py` — parses it, validates it against everything the code reads, and
  exposes the derived views the prompts and the renderer need.
- `generate.py` — regenerate the whole brand folder from any live Shopify store:
  `python -m brand.generate https://store.example.com`.
- The four `.md` files explain the *why*; `brand.yaml` is what the code parses.

**Media** — `media/`
- `movie.py` — the renderer. One `VideoClip` with a hand-written frame function:
  eased Ken Burns moves, white-backdrop product cutouts with contact shadows,
  Pillow-drawn text with real letter-spacing, cross-dissolves, progress bar.
- `voice.py` — voiceover over a pluggable TTS engine chain, falling back to a
  correctly-timed silent track that the review UI flags prominently.

**Plumbing**
- `scraper/shopify.py` — parses any public Shopify product `.json` endpoint.
- `database/` — 6-table SQLite schema, repository, seed and reset scripts.
- `worker/` — the job queue loop; `autostart.py` runs it inside Streamlit.
- `config/` — validated settings, shared retrying HTTP session, logging setup.
- `tests/` — 166 tests, no network and no API key required.

Full architecture and the decisions behind it:
[`docs/architecture/CONTEXT.md`](docs/architecture/CONTEXT.md).

## How failure is handled

The rule is that a reviewer must never be shown something misleading.

| What broke | What happens |
|---|---|
| No/invalid API key | Banner on the Dashboard; runs fail immediately, naming the setting |
| Model returns malformed JSON | Retried up to `LLM_JSON_ATTEMPTS` with the parse error fed back |
| Model returns valid JSON, wrong shape | Same retry, with the specific schema violation quoted |
| Still wrong after all attempts | Job fails, product marked `Failed`, error shown in the UI |
| Scrape fails | Job fails before any model call is billed |
| Video render fails | Version is still created — the copy is real and complete — with the error recorded |
| TTS unavailable | Silent track of the correct length; flagged loudly in the review UI |

A failed run leaves no version row and no half-written output directory: the
next run for that product cleans up whatever the failure left behind.
