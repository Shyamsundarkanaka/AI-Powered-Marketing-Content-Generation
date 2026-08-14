"""Chapters 5-7: Methodology, Resource Requirements, Software Design."""


def ch5(r):
    r.h1("Chapter 5: Project Methodology")
    r.para(
        "This project follows the Team Data Science Process (TDSP), Microsoft's agile lifecycle for "
        "analytical and intelligent applications, whose stages are business understanding, data "
        "acquisition and understanding, modelling, deployment and customer acceptance [27]. TDSP was "
        "chosen over CRISP-DM because it treats deployment and customer acceptance as first-class "
        "phases rather than a trailing step, which matches a project whose point is a reviewable "
        "artefact in a human's hands. It was adapted in two respects: data preparation is separated "
        "out, and modelling is renamed *agentic content generation*, because no model is trained.")

    r.h2("5.1  The Six Phases as Executed")
    r.para(
        "**Business understanding** established what the system had to guarantee, not merely what it "
        "had to produce. Working from the stakeholder concerns in Table 3.1, the requirement was "
        "framed around the reviewer: the reviewer is the bottleneck and the last line of defence "
        "against a false claim, and therefore must never be shown something misleading. That became "
        "the governing design rule, and the deliverable was not a document but a 173-line YAML file "
        "codifying the brand's identity, voice, banned vocabulary, personas, content limits, "
        "compliance obligations and visual system.")
    r.para(
        "**Data acquisition and understanding** rested on the observation that a Shopify product "
        "page's `.json` representation is publicly readable with no authentication [5]. Three seed "
        "products were chosen from three collections precisely so the pipeline would meet genuinely "
        "different specification tables, price points and photograph counts. That inspection surfaced "
        "the two facts that shaped the scraper: specifications arrive as an HTML `<table>` inside the "
        "description body, and the first variant listed is not reliably one a customer can buy.")
    r.para(
        "**Data preparation** is where a scraped record becomes something an agent can be held to. "
        "Specifications are separated from prose, the cheapest available variant is selected, image "
        "URLs are referenced positionally, and the record is rendered into one prompt section headed "
        "“SCRAPED PRODUCT DATA (the only facts you may use)”. Notice what preparation does *not* do: "
        "it does not clean, impute or enrich. A missing price becomes an explicit “not available” "
        "line rather than an estimate, because an imputed value would be indistinguishable from a "
        "scraped one by the time it reached the copy.")
    r.para(
        "**Agentic content generation** corresponds to TDSP's modelling stage. Five agents were "
        "specified, each with a role, a prompt builder and a validator, and wired into a LangGraph "
        "state graph of nine nodes over seven supersteps in which three of them form a genuinely "
        "parallel superstep. Two further activities belong here and are not model calls: narration "
        "is synthesised through a hosted engine with offline local fallbacks, and the video is "
        "composed deterministically by a renderer that owns its own timeline.")
    r.para(
        "**Deployment** made the pipeline operable by someone who is not its author: a Streamlit "
        "dashboard queues jobs and a review page presents results, SQLite serves as both state store "
        "and FIFO queue, and a worker consumes that queue as a daemon thread or an independent "
        "process, each run writing into an immutable versioned directory.")
    r.para(
        "**Customer acceptance and validation** begins when a version enters the `Review` state. "
        "Approval is terminal; rejection requires written feedback and optionally a scope, which "
        "cascades to any node embedding the selected node's output in its own prompt, everything "
        "outside it being carried forward byte-identically. Validation has two arms, a 174-test "
        "offline suite and an end-to-end run against a live product page. "
        "Each phase maps onto a part of the codebase, which is what makes the methodology auditable "
        "rather than decorative.")

    r.h2("5.2  Problems Encountered and Changes to the Approach")
    r.para(
        "TDSP is iterative, and several decisions were revised after evidence contradicted the "
        "original plan. Each entry in Table 5.1 was driven by an observed failure.")
    r.tbl("Table 5.1: Problems encountered and how the approach changed",
          ["Problem observed", "Original approach", "Revised approach and rationale"],
          [
              ["Model responses arrived wrapped in prose, fences, trailing commas, comments and "
               "invisible Unicode, breaking a plain `json.loads`.",
               "Parse the response directly.",
               "A four-stage extractor: keep only text blocks, strip wrappers and invisibles, take "
               "the first brace-balanced object with a string-aware scan, then three progressively "
               "destructive repairs (§8.2.1)."],
              ["The caption agent produced a 293-character first line against a 70-character limit, "
               "three attempts running, and the job failed.",
               "Validate the model's self-reported `first_line` field.",
               "Derive the first line from the caption text up to its first newline, which is what "
               "the platform actually truncates, and rewrite the prompt to explain that newline "
               "placement matters more than the hook's wording."],
              ["Piper spoke the narration in 22.37 s against a script the validator computed at "
               "22.90 s, so the planned scene timings no longer matched the audio.",
               "Pad or trim the audio to the planned video length.",
               "Rescale every scene by one factor derived from the real WAV duration, absorbing "
               "residual drift into the last scene. Padding freezes on a dead frame; trimming cuts "
               "off narration (§8.1.2)."],
              ["Rejecting a version over one weak hashtag regenerated, and re-billed, all five copy "
               "artefacts, and the caption came back different for no reason.",
               "Regenerate everything on every rejection.",
               "Scoped feedback with a dependency cascade, and byte-identical carry-forward of "
               "out-of-scope artefacts recorded as `carried_forward` (§8.3.2)."],
          ], widths=[2.9, 2.2, 4.9], size=9)


def ch6(r):
    r.h1("Chapter 6: Resource Requirement Specification")
    r.para(
        "The selection principle throughout was to minimise the number of things that must be "
        "installed, configured or paid for outside the Python environment, because each such "
        "dependency is a way the project can fail on a machine that is not the author's.")

    r.h2("6.1  Hardware and Software Requirements")
    r.para(
        "The system was developed and validated on a single Windows laptop with no GPU, and needs no "
        "more than that: four cores, 8 GB of memory with 16 GB recommended, roughly 5 MB of disk per "
        "generated version, and broadband for scraping and model calls. There is no CUDA requirement, "
        "because speech synthesis runs on CPU through ONNX Runtime and rendering is Pillow and NumPy, "
        "and no operating-system requirement beyond Windows, Linux or macOS. Video encoding is the "
        "only demanding stage: the 22.37-second clip took 115 seconds with four encoder "
        "threads. Table 6.1 lists every dependency with its pinned version.")
    r.tbl("Table 6.1: Software stack, with pinned versions",
          ["Layer", "Package", "Version", "Role"],
          [
              ["Language", "Python", "3.10+", "Uses `X | Y` union syntax throughout"],
              ["Configuration", "python-dotenv", "1.0.1", "`.env` loading for the typed settings"],
              ["Brand", "PyYAML", "6.0.3", "Parses the brand definition"],
              ["Orchestration", "langgraph", "1.2.10", "State-graph engine, typed state, reducers"],
              ["LLM adapters", "langchain-openai / -google-genai / -anthropic",
               "1.4.1 / 4.3.2 / 1.5.4", "The three interchangeable providers"],
              ["Media", "moviepy / imageio-ffmpeg", "2.2.1 / 0.6.0",
               "Encoding and muxing; **bundles the ffmpeg binary — no system install**"],
              ["Media", "pillow / numpy", "10.4.0 / 2.5.1",
               "Frame compositing, text rendering, frame buffers and the cut-out flood fill"],
              ["Speech", "elevenlabs", "1.58.0", "Hosted neural voice, leads the engine chain; needs an API key"],
              ["Speech", "piper-tts", "1.3.0", "Local offline neural voice fallback, no API key"],
              ["Testing", "pytest", "8.3.3", "174-test offline suite"],
              ["Storage", "SQLite (stdlib `sqlite3`)", "bundled",
               "State store and job queue, WAL mode [28]"],
          ], widths=[1.3, 2.7, 1.5, 3.5], size=9.5)
    r.para(
        "What is absent is as informative as what is present. There is no ORM, because the "
        "behaviour worth relying on — cascades, CHECK constraints, `ON CONFLICT` upserts — lives in "
        "SQLite rather than in a Python wrapper. There is no web framework beyond Streamlit, no "
        "ImageMagick, no system ffmpeg, no vector database and no external message broker, because "
        "SQLite is the queue.")

    r.h2("6.2  Data Requirements")
    r.para(
        "There is no training corpus and no labelled dataset: the only product facts the system may "
        "state are those scraped at run time.")
    r.tbl("Table 6.2: Data sources and provenance",
          ["Data", "Source and access method", "Volume observed"],
          [
              ["Product records", "The validated retailer's Shopify storefront; public "
               "`<product-url>.json` endpoint, unauthenticated HTTP GET [5]",
               "5 products registered; the validated product returned 15 specification rows, 989 "
               "characters of prose, a ₹75,000 price against a ₹1,07,140 compare-at price, and 16 "
               "image URLs"],
              ["Product photography", "Shopify CDN, referenced by the scraped record; cached under "
               "a SHA-1 of the URL", "10 images cached during validation"],
              ["Brand definition", "Authored for this project; regenerable from any Shopify store",
               "173 lines; 3 personas; 12 enforced content limits"],
              ["Speech model (offline fallback)", "Piper `en_US-lessac-medium` ONNX voice with "
               "JSON sidecar [21]; local file, no network at synthesis time",
               "One voice model in `data/voices/`"],
              ["Generated artefacts", "Produced by the system into immutable `output/<slug>/v<N>/`",
               "10 files, 4.7 MB, for the validated version"],
          ], widths=[1.5, 4.0, 4.5], size=9.5)

    r.h2("6.3  API, Access and Configuration Requirements")
    r.para(
        "One external service is required: a large language model API, selected by the single setting "
        "`LLM_PROVIDER`, with no part of the pipeline knowing which one is active. `openai` resolves "
        "to `ChatOpenAI` (default `gpt-5.1`), `gemini` to `ChatGoogleGenerativeAI` (default "
        "`gemini-2.5-pro`, with `gemini-2.5-flash` configured for the validated run) and `anthropic` "
        "to `ChatAnthropic` (default `claude-opus-5`). Keys are read from `.env` and never committed, "
        "and a key matching a placeholder pattern such as `changeme` is treated as absent, so the "
        "error names the real problem rather than surfacing a generic 401. A second, optional "
        "external service is the hosted speech engine, configured through `ELEVENLABS_API_KEY` and "
        "`ELEVENLABS_VOICE_ID`; when it is absent or the call fails, narration falls through to the "
        "local Piper and `pyttsx3` engines with no interruption to the run."
)
    r.para(
        "Twenty-six settings in total are read through typed helpers that fail at import with the "
        "offending variable named. Beyond the provider block, the ones that materially change "
        "behaviour are `LLM_MAX_TOKENS`, `LLM_TIMEOUT_SECONDS`, `LLM_MAX_RETRIES` (transport "
        "retries), `LLM_JSON_ATTEMPTS` (shape attempts), `WORKER_POLL_INTERVAL_SECONDS`, "
        "`VIDEO_ASPECT`, `VIDEO_FPS`, `VIDEO_RENDER_THREADS`, `TTS_ENGINES`, `ELEVENLABS_API_KEY` "
        "and `PIPER_MODEL_PATH`.")

    r.h2("6.4  Human Resources and Summary")
    r.para(
        "The project was executed individually, as the capstone guidelines require. Two external "
        "roles are assumed by the deployed system rather than by the build: a marketing reviewer who "
        "exercises the approve/reject gate, and an industry mentor who reviewed the problem framing, "
        "the architecture and the demonstration. The resource profile is deliberately modest — one "
        "laptop, one pinned environment, one API key, one local voice model — which is what makes the "
        "system demonstrable on the machine it is presented from."
)


def ch7(r):
    r.h1("Chapter 7: Software Design")
    r.para(
        "This chapter addresses Objective 1, presenting the architecture at three static levels — "
        "process topology, pipeline structure and data model — and then the dynamic views. Every "
        "decision descends from the governing rule of §5.1: a reviewer must never be shown something "
        "misleading.")

    r.h2("7.1  Architectural Overview")
    r.para(
        "The system is organised as three concerns sharing one state store, shown in Fig. 7.1. The "
        "presentation layer queues work and displays results; SQLite holds all state and is "
        "simultaneously the job queue; the execution layer owns the pipeline. The separation is the "
        "load-bearing decision: the interface stays responsive during a two-minute render because it "
        "is not doing the render, and the worker can be moved to another machine because the two "
        "communicate only through the database.")
    r.fig("fig_7_1_architecture.png",
          "Fig. 7.1: Layered architecture. The interface never performs inference; it writes a job "
          "row and reads artefacts.", width_in=3.3)

    r.h2("7.2  The Pipeline Graph")
    r.para(
        "The generation pipeline is a compiled LangGraph state graph [16] of nine nodes, shown in "
        "Fig. 7.2. Execution proceeds in supersteps: all nodes whose predecessors have completed are "
        "dispatched together, their partial states are merged, and the next superstep begins. The "
        "graph is acyclic, of fixed depth seven.")
    r.fig("fig_7_2_dag.png",
          "Fig. 7.2: The nine-node pipeline graph. Nodes 4–6 form a genuine parallel superstep; the "
          "only conditional edge is the abort path after `load_context`.", width_in=2.3)
    r.para(
        "**The fan-out is real parallelism, safe by construction.** The three branch agents read the "
        "brief and the script and write only their own state key, and the three keys they share carry "
        "explicit reducers, so LangGraph merges concurrent writes deterministically; without them the "
        "graph would silently lose two of every three artefact entries. **There is exactly one "
        "conditional edge**, gating the single condition that makes generation impossible: a product "
        "with no scraped data. **Every node is wrapped** by a tracker that records the stage and "
        "checks the cancellation flag on entry, so cancellation lands at a node boundary rather than "
        "midway through writing a file.")

    r.h2("7.3  Data Flow")
    r.para(
        "Fig. 7.3 is the level-1 data-flow diagram: three external entities, five processes and three "
        "data stores. It makes explicit the property the design turns on, that product facts enter "
        "the system exactly once, through P2, and every downstream process reads them from the store "
        "rather than from the network. The brand definition D3 reaches both the copy and media "
        "processes, which keeps the words an agent writes and the colours the renderer paints derived "
        "from the same authority.")
    r.fig("fig_7_3_dfd.png",
          "Fig. 7.3: Level-1 data-flow diagram. The scraped record in D1 is the only path by which "
          "a product fact can reach the copy-generation process P3.", width_in=3.3)

    r.h2("7.4  Data Model")
    r.para(
        "Six tables hold all state, shown in Fig. 7.4, with status values enumerated by SQL CHECK "
        "constraints rather than in application code. Three constraints encode correctness "
        "properties: `UNIQUE (products.url)` makes seeding idempotent, `UNIQUE (product_id, "
        "version_number)` makes a version immutable, and `versions.job_id` is `ON DELETE SET NULL` "
        "while every other foreign key cascades, because deleting a job's history must not delete the "
        "version it produced.")
    r.fig("fig_7_4_erd.png",
          "Fig. 7.4: Entity–relationship model. Six tables, five indexes, and CHECK-constrained "
          "status enumerations.", width_in=3.3)
    r.para(
        "The most consequential decision is invisible in the diagram: **the version row is created "
        "last.** The pipeline reserves the next version number without inserting a row, lays out the "
        "`v<N>/` directory, writes every artefact into it, and only then inserts the version row. A "
        "version row is a promise that there is something to review, so making it the last write "
        "means a run that dies part way through leaves files on disk but no empty version staring at "
        "a reviewer.")

    r.h2("7.5  Request Lifecycle and Job State Model")
    r.para(
        "Fig. 7.5 traces a run from the reviewer's click to the reviewer's decision, making visible "
        "where the retry loop sits and how the interface learns the run has finished. Configuration "
        "is checked before the scrape, because scraping first and then discovering there is no usable "
        "API key wastes a request and reports the failure against the wrong stage.")
    r.fig("fig_7_5_sequence.png",
          "Fig. 7.5: Request lifecycle. The interface polls every two seconds while a job is "
          "active; the worker polls for work every five.", width_in=3.3)
    r.para(
        "A job reaches one of four terminal states from `Running`, and the product's status mirrors "
        "it with a `Review` state added before the reviewer's decision. One guarantee matters "
        "operationally: a job can only be `Running` while a live worker holds it in memory, so a "
        "worker that starts up and finds one knows the previous process died. Reclaiming those jobs "
        "prevents the active-job count from being permanently non-zero.")

    r.h2("7.6  Brand as Data")
    r.para(
        "Fig. 7.6 shows the dependency that makes the system re-targetable: a single YAML document is "
        "the authority for what agents may say, what validators enforce and what the renderer draws. "
        "There is no hard-coded colour value, tone rule or numeric content limit anywhere in the "
        "Python. The consequence was observed during this project: tightening the brand's "
        "script-duration window changed what the validator accepts with no code change and, as §9.4 "
        "reports, immediately broke three tests written against the previous window.")
    r.fig("fig_7_7_brand_as_data.png",
          "Fig. 7.6: The brand definition as the single authority for prompts, validation limits "
          "and rendered visuals.", width_in=2.9)

    r.h2("7.7  Design Decisions and Rationale")
    r.tbl("Table 7.1: Design decisions and the alternatives rejected",
          ["Decision", "Alternative considered", "Why the alternative was rejected"],
          [
              ["LangGraph state graph with a fixed topology",
               "A hand-written sequential function, or a conversational multi-agent framework [14]",
               "The three-way fan-out is a real parallel superstep; hand-rolling it means writing "
               "thread coordination and merge logic. A conversational framework makes the number of "
               "billed model calls emergent."],
              ["SQLite as both state store and queue [28]", "PostgreSQL with Redis or Celery",
               "Single-machine deployment; the required semantics fit in six tables, and WAL mode "
               "makes concurrent thread access safe without a broker."],
              ["Deterministic renderer over still photography, with Pillow for all text",
               "Generative video synthesis [18]; MoviePy's `TextClip`",
               "A diffusion model asked for a specific product produces a plausible-looking item, "
               "not that one, and the authoritative product photography already exists. `TextClip` shells "
               "out to ImageMagick, a classic deployment failure."],
              ["Fail the run rather than emit fallback copy",
               "Return a template or a cached response on failure",
               "A fallback is indistinguishable from real output at the point where a human "
               "approves it. This is the governing rule of the whole design."],
          ], widths=[2.2, 2.2, 5.6], size=9)
