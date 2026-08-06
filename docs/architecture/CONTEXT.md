# Architecture

The system takes a Shopify product URL and produces a complete, reviewable
marketing content package: campaign brief, voiceover script, caption, hashtags,
a narration track and a rendered 1080×1920 vertical video — then routes it
through a human approve/reject loop where a rejection regenerates with the
reviewer's feedback.

## The governing rule

**A reviewer must never be shown something misleading.** Every design decision
below follows from that. It is why there is no placeholder content anywhere in
the system, why validation is strict about claims and lenient about formatting,
why a silent voiceover is flagged on the review page rather than in a log file,
and why a failed run deletes its own half-written output directory.

The specific failure this rules out: marketing copy that reads plausibly, is
brand-shaped, quotes the right product name, and was written by nobody. That is
worse than an error message, because it can be approved and published.

## Shape

```
Streamlit UI  ──writes jobs──▶  SQLite  ──polled by──▶  Worker
     ▲                            ▲                        │
     └────── reads versions ──────┘                        ▼
                                                    LangGraph pipeline
```

SQLite is the single source of truth. The UI never runs inference; it queues a
job and reads results. The worker owns the pipeline. This split is what lets the
UI stay responsive during a two-minute render, and lets `python -m worker.run`
be moved to another machine without touching the UI.

For local use `worker/autostart.py` runs the worker loop on a daemon thread
inside the Streamlit process, so one command runs everything and a job can never
sit `Pending` because nothing was alive to process it.

## The pipeline

```
                    load_context
                         │  (fails fast if the product has no scraped data)
                    campaign_brief
                         │
                       script
                      ╱   │   ╲          three independent agents, one superstep
                 caption hashtags video_plan
                      ╲   │   ╱
                     voiceover           needs the script; joins the fan-out
                         │
                    render_video         needs the plan and the audio
                         │
                      finalize           writes files, registers outputs, opens review
```

The fan-out is real parallelism in LangGraph terms. It works because those three
nodes write disjoint state keys, and the keys they *share* (`artifacts`,
`warnings`, `sources`) carry reducers in `graph/state.py`.

Each agent node is a plain `PipelineState -> dict` function. Nothing in
`nodes.py` builds the graph, so nodes stay individually callable and testable.

## Generation contract

Every agent call goes through `graph/llm.py::generate_json()`, which is also the
only place the system gives up. The sequence:

1. Build the prompt. `graph/prompts.py` injects the whole brand definition and
   states the hard rule on facts: the scraped product row is the only source of
   product facts, and a number that isn't in it may not be written.
2. Call the provider. Transport failures are retried by the client itself.
3. Parse. `extract_json()` handles fences, prose preambles, trailing prose
   containing braces, trailing commas, `//` and `/* */` comments, and — only as a
   last resort, once the document has already failed to parse — curly quotes used
   as delimiters. It scans for a brace-balanced object with string/escape
   awareness rather than `find("{") … rfind("}")`.
4. Validate against the node's schema in `graph/schemas.py`.
5. On a shape failure, re-ask with the model's own bad output and the specific
   error appended, up to `LLM_JSON_ATTEMPTS` times.
6. If it still fails: raise. The run fails, the job is marked `Failed`, the
   product shows the error, and no version row is created.

### Validation philosophy

`graph/schemas.py` splits every rule into one of two buckets:

- **Normalize** what the code can fix correctly: a hashtag missing its `#`,
  an image index past the end of the array, a scene duration of `"4.5 seconds"`,
  a `char_count` the model miscounted, an unknown scene `kind`. Round-tripping to
  the model for these would be slower and no more correct.
- **Reject** what needs judgement: a persona id that doesn't exist, a caption
  over the character limit, a script that is 12 seconds long when the brand calls
  for 25–32, a plan that doesn't open on a title card. Only the model can fix
  those, so the error message is written as an instruction to it.

Two validations are worth calling out because they prevent silent breakage:

- **Script duration is recomputed, never trusted.** The model's own
  `estimated_duration_seconds` is a guess it is bad at, and the voiceover length
  and every scene duration are derived from it. The word count is a fact, so the
  duration is computed from it and the model's claim is discarded.
- **The caption's first line is derived from the caption**, not from the
  `first_line` the model reports, because what the platform truncates is the real
  first line.

## Brand as data

`brand/brand.yaml` is the machine-readable source of truth for voice, personas,
language rules, content rules, compliance boundaries, palette, typography and
video geometry. Two consumers read it: `graph/prompts.py` injects the copy-facing
sections into every agent prompt, and `media/movie.py` reads `visual` for the
render. There is no hard-coded hex value or content rule anywhere in the code.

`brand/loader.py` validates the document against every path the code reads,
reporting all problems at once. Without that, a brand file missing
`content_rules.script.words_per_second` parses fine, loads fine, and then dies
with a bare `KeyError` inside the voiceover node partway into a paid run.

`python -m brand.generate <store-url>` regenerates the whole folder — YAML plus
the four prose companions — from any live Shopify store, via five focused
prompts. It writes nothing unless all five succeed and the assembled document
validates.

## Review and the feedback loop

A version is immutable once created. Rejecting one requires written feedback and
queues a regeneration; the next run reads the feedback off the rejected row and
makes it the primary instruction in every prompt.

Feedback can be **scoped** to specific parts. Scoping cascades downstream —
selecting `script` forces `caption`, `hashtags` and `video_plan` too, because all
three embed the script in their prompts and would otherwise pair new narration
with copy written against the old version. Anything outside the scope is carried
forward byte-identical from the previous version's `_meta.json` rather than
regenerated, which saves both the call and the risk of an unrelated part drifting.

Only the *current* version's rejection counts. An older rejection that a later
version already answered is finished business; re-applying it would make every
future run keep rewriting to feedback the reviewer gave once and already got a
response to.

## Rendering

`media/movie.py` is one `VideoClip` with a hand-written frame function rather
than a stack of MoviePy effects and `concatenate_videoclips`. Owning the timeline
is what makes eased (not linear) camera movement, text pinned while the image
moves behind it, and dissolves on a known curve exact and deterministic.

Text is drawn with Pillow, not `TextClip` — that avoids ImageMagick and font
discovery failures entirely, and buys letter-spacing, drop shadows, measured
wrapping and rounded pill backgrounds.

Per-scene work is done once: each scene bakes a background canvas at `zoom_end`
resolution and a static text overlay up front, so every frame is a *downscale* of
an oversampled source and the zoom stays sharp. Product shots are cut out of
their white studio backdrop by border-seeded flood fill, so the product floats in
the frame with a contact shadow instead of reading as a pasted rectangle.

Scene durations are rescaled to the **real** narration length read from the WAV
header, not to the plan's estimate — otherwise the picture drifts against the
audio by however much the TTS engine differed from the words-per-second
heuristic.

## Voiceover

`TTS_ENGINES` is an ordered chain; the first engine that produces a valid WAV
wins. Each engine synthesises to a scratch path that is verified and only then
moved into place, so a crashed engine can never leave a truncated file that the
renderer would treat as real audio.

If every engine fails, the track is digital silence of the script's measured
duration — the video still times correctly and a real narration WAV can be
dropped in later without re-rendering — and the review page says so in a banner
above the video. Adding a hosted/paid engine is one function and one registry
entry; see the `media/voice.py` docstring.

## Data model

Six tables, all in `database/schema.sql`:

| Table | Holds |
|---|---|
| `products` | name, source URL (UNIQUE), lifecycle status, output directory |
| `scraped_data` | one row per product: title, description, price, images, specs |
| `jobs` | queue: status, current stage, cancel flag, error message |
| `versions` | immutable generated versions, reviewer feedback and its scope |
| `outputs` | one row per artifact file, per version |
| `logs` | per-product/per-job activity trail shown in the UI |

Product lifecycle: `Pending → Running → Review → Approved | Rejected | Failed |
Cancelled`. Foreign keys cascade, so deleting a product removes its jobs,
versions, outputs, scraped data and logs; `delete_product_with_files()` removes
the DB row first and the directory second, so a product can never be left
pointing at files that no longer exist.

SQLite runs in WAL mode with a 30s busy timeout so the worker thread and the
Streamlit polling thread can share the file without lock errors.

## Consistency guarantees

- **A version row exists only when every artifact is on disk.** `finalize`
  creates it last. A run that dies earlier leaves a directory but no row.
- **Orphaned directories are cleaned up.** `discard_orphan_version_dirs()`
  removes any `v<N>/` with no `versions` row behind it, so the output tree only
  contains versions a reviewer can open.
- **A job always reaches a terminal status.** `reclaim_stale_jobs()` fails any
  job still `Running` at worker startup — it can only be `Running` while a live
  process holds it, so finding one means the previous process died. Without this,
  `count_active_jobs()` stays non-zero forever and every Run button is disabled.
- **Cancellation is cooperative**, checked at node boundaries, so a run is never
  interrupted mid-stage and lands within one stage's duration.

## Testing

`pytest` — 166 tests, no network and no API key. The provider client is replaced
with a scripted fake, so the retry/give-up logic is exercised directly; the
database tests run against a real temporary SQLite file, because the behaviour
worth testing (cascades, UNIQUE constraints) lives in SQLite itself.
