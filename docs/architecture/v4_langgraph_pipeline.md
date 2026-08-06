# Step 4 — Brand System, LangGraph Pipeline, Voiceover & Video

Status: **Done**. This file is a permanent record of Step 4 as shipped. It is not
edited after later steps land — new steps get their own `vN_...md` file in this
folder. See `CONTEXT.md` for the current pointer and running summary.

This step closes roadmap items 1–4 from `CONTEXT.md` in one pass: the LangGraph
workflow and AI agents, voiceover, video plan and rendering, and the
reviewer-feedback-as-context loop.

## 1. What this step builds

A job no longer just scrapes. It now runs a LangGraph pipeline over the scraped
data and produces a complete, reviewable version:

| Artifact | File | Produced by |
|---|---|---|
| campaign_brief | `campaign_brief.md` (+ `.json`) | Claude agent |
| script | `script.md` (+ `.json`) | Claude agent |
| caption | `caption.txt` | Claude agent |
| hashtags | `hashtags.txt` | Claude agent |
| video_plan | `video_plan.json` | Claude agent |
| voiceover | `voiceover.wav` | `media/voice.py` |
| video | `video.mp4` | `media/movie.py` |

Plus `_meta.json`, a provenance sidecar the review UI reads (see §6).

## 2. The brand system (`brand/`)

Decided with the user: brand definition lives in a folder, is loaded into every
agent prompt, **and** drives the renderer.

```
brand/
  brand.yaml            # machine-readable — the only file code parses
  loader.py             # load_brand() -> Brand; prompt_block(), color(), font_candidates()
  BRAND_GUIDELINES.md   # voice, principles, banned vocabulary, per-artifact rules
  PERSONAS.md           # 3 personas + the selection rule
  VISUAL_IDENTITY.md    # palette, type, safe areas, motion, scene grammar
  COMPLIANCE.md         # the guardrails, and where each is enforced
```

Two consumers, one parse:

- `graph/prompts.py` injects `brand.prompt_block()` — brand, voice, audience,
  language, content rules, compliance — verbatim into **every** agent system
  prompt. Editing `brand.yaml` changes agent behaviour with no code change.
- `media/movie.py` reads the `visual` block for colours, fonts, safe areas, Ken
  Burns amounts and card durations. There is no hard-coded hex in the renderer.

The brand content itself was authored for this system from Radboards' catalogue
and market position — it is a working definition, not a document from the
company, and `BRAND_GUIDELINES.md` says so.

**The single compliance rule everything else follows from:** agents may state
only what the scraped row supports. They are given `scraped_data` and nothing
else about the product, precisely so there is no other place an invented "50 km
range" could come from.

## 3. The graph (`graph/`)

```
load_context
     │  (conditional edge: abort if the product has no scraped_data)
campaign_brief
     │
   script
  ╱   │   ╲            three independent agents in one superstep
caption hashtags video_plan
  ╲   │   ╱
 voiceover              joins the fan-out; needs the script
     │
render_video            needs the plan and the audio
     │
  finalize              writes files, registers outputs, opens review
```

The fan-out is real LangGraph parallelism — the three branches dispatch together
and `voiceover` waits for all of them. It works because those nodes write
disjoint state keys; the keys they *share* (`artifacts`, `errors`, `sources`)
carry reducers in `graph/state.py` (`operator.add`, and a dict merge for
`sources`).

Files:

```
graph/
  state.py      # PipelineState TypedDict + reducers
  llm.py        # the one place we call Claude, and the one place we give up
  prompts.py    # per-agent system/user prompts + required JSON keys
  stubs.py      # documented fallback output per node
  nodes.py      # the 9 node functions
  pipeline.py   # topology, run_pipeline(), `python -m graph.pipeline <id>` CLI
```

Model: `claude-opus-5` via `langchain-anthropic`. Agents are asked for a single
JSON object; `llm.py` extracts it (bare, fenced or with preamble), validates the
required keys, and treats a shape violation the same as a network failure.

## 4. Dummy-key behaviour (decided with the user)

`ANTHROPIC_API_KEY` defaults to a placeholder. Every agent call is genuinely
attempted, returns 401, and the node falls back to **its documented stub output**
— not a `"TODO"`, but a realistic, brand-correct example of exactly that node's
shape, built from the real scraped data (real name, real price, real specs, real
image count).

That matters more than it sounds: because the stubs are real data in the real
shape, the downstream nodes exercise the same code paths they would with live
model output. The video plan is renderable, the timing is right, and the MP4 is
a genuine artifact rather than a mock.

Provenance is recorded everywhere, per the user's decision:

- `payload["_source"]` = `"llm"` or `"stub"` on every artifact JSON
- a `WARNING` row in `logs` per stubbed node, with the underlying error
- `_meta.json` carries `sources`, `stubbed_nodes` and `errors`
- the Output tab shows a `STUB` badge per artifact and a banner per version

Setting a real key in `.env` makes it live with zero code changes.

## 5. Voiceover — silence, deliberately (`media/voice.py`)

No TTS provider is wired up. The default output is digital silence of **exactly
the script's estimated spoken duration**, written with the stdlib `wave` module.
So video timing, scene pacing and the audio stream are all already correct, and
a real narration WAV of the same length can be dropped in without touching
anything else. `kind` is `"silence"` or `"tts"` and flows through to the UI.

Setting `ENABLE_TTS=true` (with `pyttsx3` installed) attempts real offline
speech first and falls back to silence.

## 6. Video rendering (`media/movie.py`)

1080×1920 vertical, 30fps, ~19–30s, MP4/H.264 + AAC, `yuv420p`. `VIDEO_ASPECT`
also accepts `square` and `landscape`; safe areas scale proportionally.

Four decisions worth recording:

**One `VideoClip` with a hand-written frame function**, rather than a stack of
MoviePy effects and `concatenate_videoclips`. Owning the timeline is what makes
eased (not linear) camera movement, text that stays pinned while the image moves
behind it, and dissolves on a known curve exact and deterministic.

**Text is drawn with Pillow, not `TextClip`** — no ImageMagick/font-discovery
failure modes, plus letter-spacing, drop shadows, measured wrapping and rounded
spec pills. Fonts resolve through the `brand.yaml` candidate chain and end at
Pillow's default, so a missing typeface never fails a render.

**The white studio backdrop is cut out of product photography.** Shopify shots
are on pure white; pasted as a rectangle they read as a sticker and destroy text
contrast. The white *connected to the image border* is flood-filled (at 1/4
scale, then feathered) so white that belongs to the product — these boards have
white graffiti prints — survives. The product then floats on a blurred, darkened
backdrop with a soft contact shadow. This was the single biggest visual
improvement in the step.

**Per-scene work is done once.** Each scene bakes a high-resolution background
(at `zoom_end` resolution, so every frame is a downscale and the zoom stays
sharp) and a static text overlay; per frame the renderer only crops, resizes and
composites. A 19-second 1080×1920 render takes tens of seconds.

Also: a thin progress bar along the bottom safe edge, and image downloads cached
in `data/assets/` by URL hash so re-rendering v2 after a rejection costs no
network.

## 7. Reviewer-feedback loop (roadmap item 4)

Rejecting a version in the Output tab now:

1. requires typed feedback (it is what makes v2 different),
2. stores it on the version row and flips the product to `Rejected`,
3. **queues a job immediately** (decided with the user — no manual re-queue).

On the next run, `load_context` finds the most recent rejected version, reads its
`_meta.json` off disk for the previous copy, and `prompts.revision_directive()`
injects both into every agent prompt as an explicit rewrite brief. `_meta.json`
records `revision_of_feedback`, and the UI shows "Generated in response to: …".

Reading the previous output off disk rather than holding it in memory is what
lets a rejection from last week feed a run started today.

## 8. Version rows are created at the end, not the start

`load_context` reserves a version *number* and directory via
`next_version_number()`; `finalize` creates the `versions` row once artifacts
exist. A run that dies mid-way now leaves files on disk and a `Failed` job
rather than an empty version sitting in `Review` — which is exactly what an
early crash during this step's development produced.

## 9. Changes to existing files

| File | Change |
|---|---|
| `config/settings.py` | + `BRAND_DIR`, `ASSET_CACHE_DIR`, Claude settings, media settings |
| `database/repository.py` | + `next_version_number()` |
| `worker/run.py` | job = scrape **then** `run_pipeline()`; product ends in `Review` |
| `streamlit_app/pages/1_Output.py` | inline artifact rendering (video/audio players, markdown, STUB badges), reject-and-requeue, per-product log panel |
| `requirements.txt`, `.env.example` | new dependencies and settings |

`streamlit_app/app.py` is unchanged — it still never imports `graph` and never
calls a model.

## 10. Verified end to end

Ran against live data on Windows with the placeholder key:

- `python -m graph.pipeline 1` — 7 artifacts, all 5 agents stubbed, video rendered
- worker path (`create_job` → `process_job`) — scrape + pipeline + `Review`
- reject with feedback → auto-queued job → v2 whose prompts carry the revision
  block and whose `_meta.json` records the feedback
- `python -m media.movie --product-id 5` standalone render
- all three aspect ratios produce frames
- Streamlit app and Output page both return 200 with no exceptions

## 11. Explicitly out of scope for Step 4

- **Real TTS** — silence by default, `pyttsx3` behind a flag (§5).
- **Testing strategy** — still nothing automated; every check above was manual.
  This is now the largest gap.
- **Worker crash recovery** — a killed worker still leaves a job/product stuck in
  `Running` (unchanged from Step 3; the orphan *version* problem is fixed, §8).
- **Concurrency** — still one job at a time.
- **Banned-phrase enforcement in code** — the banned vocabulary is in the prompt
  and in `COMPLIANCE.md`, but nothing programmatically rejects a violating
  generation; the human reviewer is the backstop.
- **Music, b-roll, motion graphics, subtitles** in the video.

## 12. Decisions explicitly made with the user (don't re-litigate)

- LangGraph + `langchain-anthropic` (not the raw SDK, not a provider-agnostic
  adapter), so a real key swaps in with no code change.
- Dummy key by default; on failure each node returns its documented stub output.
- Stub content is **marked everywhere** — artifact JSON, logs, and a visible
  badge in the UI. No silent fallback.
- Voiceover is a silent track of the correct duration, not "no audio track".
- Video is 1080×1920 vertical, ~25–30s, Ken Burns over scraped photography.
- Brand lives in `brand/` as markdown + `brand.yaml`, loaded into every prompt
  *and* read by the renderer.
- Rejection auto-queues the regeneration; feedback is injected into every agent
  prompt for the next version.
