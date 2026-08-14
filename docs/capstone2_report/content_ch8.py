"""Chapter 8: Implementation."""

REPO = "https://github.com/Shyamsundarkanaka/AI-Powered-Marketing-Content-Generation"


def ch8(r):
    r.h1("Chapter 8: Implementation")
    r.para(
        "This chapter is organised to match Chapter 4: §8.1 implements Objective 2, §8.2 Objective 3 "
        "and §8.3 Objective 6. Objective 1 is addressed in Chapter 7. The delivered system is "
        "6,488 lines of application Python across eight packages — "
        "`config/` 272, `database/` 840, `brand/` 881 plus 173 lines of YAML, `scraper/` 235, "
        "`graph/` 1,925, `media/` 1,361, `worker/` 189 and `streamlit_app/` 840 — plus a 1,345-line "
        "test suite.")
    r.para(f"**Repository:** {REPO}")

    # =====================================================================
    r.h2("8.1  Implementation of Objective 2 — Scraping, Data Layer, Agents and Media")
    r.para(
        "**Objective 2:** build the end-to-end generation pipeline — scraper, persistence, five LLM "
        "agents, speech synthesis and a deterministic renderer — with every brand rule externalised "
        "into a single machine-readable file.")

    r.h3("8.1.1  Scraper, data layer and prompt construction")
    r.para(
        "The scraper is 139 lines because it exploits the public JSON representation of a product "
        "page [5] rather than parsing rendered HTML. Two of its decisions are correctness decisions: "
        "every `<table>` in the description body is parsed into key/value pairs and then removed "
        "before the prose is extracted, so the description handed to the model does not repeat the "
        "specification rows; and among priced variants, available ones are preferred and the cheapest "
        "chosen. A malformed price becomes `None` with a warning, but a fetch failure or a missing "
        "product object raises. Facts may be absent; they may not be invented.")
    r.para(
        "Every agent's system prompt is assembled by one function. The brand block is rendered from "
        "the YAML document and injected verbatim, but only the sections an agent can act on. The user "
        "message carries the fact block, the task and a `# JSON KEYS` section that must correspond "
        "precisely to the matching validator, because a response the prompt asks for but the "
        "validator rejects would loop until the attempt budget is exhausted.")
    r.tbl("Table 8.1: The five generation agents",
          ["Agent", "Role given to the model", "Context",
           "Key constraints enforced by its validator"],
          [
              ["`campaign_brief`", "Senior performance marketing strategist", "Fact block",
               "Exactly one persona chosen from the brand's three ids; at least three proof points, "
               "each naming the scraped spec, price or description line it came from"],
              ["`script`", "Short-form video copywriter", "Fact block + brief",
               "Exactly five beats in the order hook, problem, product_reveal, proof, cta; hook ≤ 12 "
               "words; spoken length recomputed from word count and required to land in the brand's "
               "32–40 s window"],
              ["`caption`", "Social copywriter", "Fact block + brief + script",
               "≤ 300 characters; derived first line ≤ 70 characters; a call to action; no hashtags "
               "inside the caption"],
              ["`hashtags`", "Social strategist", "Fact block + brief",
               "8–12 lowercase tags; the brand's mandatory tag always inserted first; five named "
               "tags banned; duplicates dropped"],
              ["`video_plan`", "Short-form video director", "Fact block + script",
               "5–7 scenes, one per beat, in beat order; first scene `title` and last `cta`; every "
               "scene names a valid image index; spec pills copied verbatim from the scraped specs"],
          ], widths=[1.2, 2.0, 1.6, 5.2], size=9.5)

    r.h3("8.1.2  Graph assembly, speech synthesis and video rendering")
    r.para(
        "The topology of Fig. 7.2 is twelve lines of graph construction, of which the loop is what "
        "creates the parallel superstep. Concurrent writes are made safe by reducers on the shared "
        "state: keys written by one node use last-write-wins, while the three accumulator keys carry "
        "explicit merge functions. There is deliberately no per-node error field, because a copy node "
        "either produces valid content or raises.")
    r.para(
        "Narration comes from an ordered chain of engines, the first producing a valid WAV winning: "
        "ElevenLabs, a hosted neural voice reached through its API and needing a key, then Piper, a "
        "local VITS-derived ONNX neural voice [20], [21] needing no key and no network, then "
        "`pyttsx3`. An engine synthesises to a `.partial.wav` path and the file is moved into place "
        "only once it exists, is non-empty and yields a readable duration, so a half-written file can "
        "never be picked up as real audio.")
    r.para(
        "The renderer is the largest module at 1,074 lines, and four commitments shape it: everything "
        "visual is read from the brand file; the whole video is one `VideoClip` with a hand-written "
        "frame function; all text is drawn with Pillow; and per-scene work is done once, so each "
        "frame only crops, resizes and alpha-composites. The product is lifted off its studio "
        "backdrop by a border-seeded flood fill rather than a global white threshold.")
    r.para(
        "**Retiming the scenes to the real narration** is the most subtle correctness fix. The shot "
        "plan's durations are only an estimate from a words-per-second heuristic, and in the "
        "validated run the script measured 22.90 s while Piper spoke it in 22.37 s. Padding the audio "
        "freezes the last frame on silence and trimming it cuts off narration, so every scene is "
        "instead rescaled by a single factor derived from the WAV header.")

    # =====================================================================
    r.h2("8.2  Implementation of Objective 3 — Fact Grounding and Validation")
    r.para(
        "**Objective 3:** implement hard-fact prompting, hardened JSON extraction, brand-derived "
        "schema validation with an explicit normalise-versus-reject split, an error-fed repair-retry "
        "loop, and a no-fallback rule. The hard-fact rule is a fixed block in every system prompt, "
        "telling the model that the scraped product data is its only source of product facts and that "
        "a missing fact must be written around, never estimated.")

    r.h3("8.2.1  Hardened JSON extraction")
    r.para(
        "Models are asked to return a single JSON object and frequently do not. The responses that "
        "had to be handled included objects wrapped in prose or markdown fences, trailing commas, "
        "comments, curly quotation marks used as delimiters, zero-width Unicode, a single-element "
        "array wrapping the object, and, from reasoning models, text interleaved with thinking "
        "blocks.")
    r.fig("fig_8_1_json_pipeline.png",
          "Fig. 8.1: The four-stage JSON extraction and repair pipeline.", width_in=2.6)
    r.para(
        "Stage one keeps only content blocks whose type is `text`, since concatenating everything "
        "would drop a reasoning model's chain of thought into the parser. Stage three is the piece "
        "most implementations get wrong: the obvious slice from the first `{` to the last `}` breaks "
        "on an object followed by prose containing a brace, and on two objects in a row. The scanner "
        "below returns the first brace-balanced object instead.")
    r.code([
        "def _first_json_object(text: str) -> Optional[str]:               # graph/llm.py",
        "    start = text.find(\"{\")",
        "    if start == -1: return None",
        "    depth = 0; in_string = False; escaped = False",
        "    for index in range(start, len(text)):",
        "        char = text[index]",
        "        if in_string:",
        "            if escaped:            escaped = False",
        "            elif char == \"\\\\\":      escaped = True",
        "            elif char == '\"':       in_string = False",
        "            continue",
        "        if   char == '\"': in_string = True",
        "        elif char == \"{\": depth += 1",
        "        elif char == \"}\":",
        "            depth -= 1",
        "            if depth == 0: return text[start : index + 1]",
        "    return None",
    ])

    r.h3("8.2.2  Brand-derived validators and the normalise/reject split")
    r.para(
        "Each agent has a validator returning a normalised copy of the payload or raising with a "
        "message phrased as an instruction rather than as a diagnostic, so it can be handed straight "
        "back to the model. The decision that defines the module is the split in Table 8.2 between "
        "what the code fixes and what only the model can fix.")
    r.tbl("Table 8.2: What is normalised locally versus what is rejected and re-asked",
          ["Bucket", "Rule", "Examples observed"],
          [
              ["Normalise", "Anything the code can fix correctly and unambiguously",
               "A hashtag missing its `#`; `\"#Ride To Work!\"` becomes `#ridetowork`; an image "
               "index past the end of the list is wrapped modulo the count; `\"4.5 seconds\"` is "
               "parsed to `4.5`; an unknown scene kind becomes `feature`; a bare-string proof point "
               "becomes `{claim, source: \"unattributed\"}`"],
              ["Reject and re-ask", "Anything requiring judgement",
               "A persona id that does not exist in the brand file; a caption over 300 characters; "
               "a derived first line over 70; a script whose recomputed spoken length falls outside "
               "the brand's window; wrong or duplicated beat names; a shot plan not opening on a "
               "title card or closing on a call to action"],
          ], widths=[1.2, 2.3, 6.5], size=9.5)
    r.para(
        "Every limit is read from the brand file, so tightening a brand rule tightens validation with "
        "no code change. The most consequential validator is the script's: it discards the model's "
        "duration estimate and recomputes the spoken length from the word count, because the estimate "
        "is a guess whereas the word count is a fact, and that duration is what the video timeline is "
        "built from.")

    r.h3("8.2.3  The repair-retry loop and the no-fallback rule")
    r.para(
        "On a schema error the model's own bad output is appended to the conversation, followed by "
        "a correction quoting the specific violation, and the call is repeated up to the configured "
        "budget:")
    r.code([
        "for attempt in range(1, settings.LLM_JSON_ATTEMPTS + 1):          # graph/llm.py",
        "    try:",
        "        response = model.invoke(messages)",
        "    except Exception as exc:",
        "        raise LLMUnavailableError(f\"{node}: {config.name} call failed: ...\")",
        "    raw = response_text(getattr(response, \"content\", response))",
        "    try:",
        "        payload = validator(extract_json(raw))",
        "    except SchemaError as exc:",
        "        repairs.append(str(exc))",
        "        if attempt == settings.LLM_JSON_ATTEMPTS: break",
        "        messages.append(AIMessage(content=raw[:4000]))        # its own bad output",
        "        messages.append(HumanMessage(content=_REPAIR_TEMPLATE.format(error=exc)))",
        "        continue",
        "    return LLMResult(payload, config.name, config.model, attempt, tuple(repairs))",
        "",
        "raise MalformedResponseError(f\"{node}: ... after N attempts. Last error: ...\")",
    ])
    r.para(
        "Transport retries for connection resets and HTTP 429 or 5xx are performed by the provider "
        "client; this loop performs only shape retries, because re-asking a dead endpoint merely "
        "delays the failure. If the budget is exhausted the job fails with the last schema error "
        "attached. There is no canned copy anywhere in the codebase to fall back to, asserted "
        "mechanically by `test_never_substitutes_content_on_failure`. One exception is reasoned "
        "rather than expedient: a **video render failure** produces a version anyway, because the "
        "copy is real and reviewable without the MP4.")
    r.tbl("Table 8.3: Failure taxonomy and system response",
          ["Condition", "Response", "Where handled"],
          [
              ["**Missing or placeholder API key**",
               "Red banner on the dashboard; runs fail immediately naming the exact setting",
               "`check_configuration()`"],
              ["**Provider quota exhausted (429) or model unavailable (404)**",
               "Transport retries, then the job fails with the provider's message preserved",
               "provider client, `generate_json()`"],
              ["**Unparseable text, or valid JSON of the wrong shape**",
               "Retried with the parse position or the specific schema violation quoted",
               "`extract_json()`, `graph/schemas.py`"],
              ["**Still wrong after the attempt budget**",
               "Job and product `Failed`; last error shown in the interface; nothing substituted",
               "`generate_json()`"],
              ["Images unfetchable, no font found, or every speech engine fails",
               "Warning appended; gradient or default font substituted for the *visual* only; "
               "correctly-timed silent track plus a banner in the review page",
               "`ImageLibrary`, `FontBook`, `media/voice.py`"],
              ["Video render fails", "**Version is still created**; the copy is real and complete",
               "`nodes.render_video`"],
              ["Cancellation, a killed worker, or a run that dies before finalisation",
               "Honoured at the next node boundary, or failed by the next start-up's reclamation; "
               "no version row, and the orphaned directory is removed",
               "tracking wrapper, `reclaim_stale_jobs()`"],
              ["Brand file missing a key / bad `.env` value",
               "**All** problems reported at once at load; configuration error at import naming the "
               "variable", "`validate_brand_document()`, `config/settings.py`"],
          ], widths=[2.9, 3.6, 2.5], size=9)

    # =====================================================================
    r.h2("8.3  Implementation of Objective 6 — Deployment and the Review Application")
    r.para(
        "**Objective 6:** deploy the system as a demo-ready, single-command application with an "
        "embedded worker, a SQLite-backed queue, immutable versioned outputs, and a human "
        "approve/reject gate whose rejections carry scoped feedback.")

    r.h3("8.3.1  Worker, queue and interface")
    r.para(
        "The worker polls for the oldest pending job, transitions it to `Running` and processes it. "
        "The order of operations is chosen so a failure is reported against the stage that caused it: "
        "status transitions and a log row, a cancellation check, configuration validation, the "
        "scrape, then the pipeline. The transition to `Completed` sits inside the same `try` block as "
        "the pipeline call, so a failure there still resolves the job to `Failed`.")

    r.h3("8.3.2  The review gate, scoped feedback and the cascade")
    r.para(
        "The review page presents the rendered video and its audio, the caption and hashtags side by "
        "side, an optional details panel with the brief, script, shot plan and provenance, and the "
        "approve/reject controls.")
    r.fig("fig_8_6_hitl.png", "Fig. 8.2: The human-in-the-loop review and regeneration loop.",
          width_in=2.6)
    r.para(
        "Rejection requires written feedback, because feedback is what makes the next version "
        "different. The reviewer may scope it to the script, caption, hashtags or shot plan; the "
        "brief is not offered, because a viewer judging a finished video has no visibility into it. "
        "That scope is expanded through a dependency cascade: if a node is in scope, every node "
        "embedding its output in its own prompt must be too, otherwise the new version would pair a "
        "regenerated script with a caption written against the old one — output that is inconsistent, "
        "reads perfectly well, and is wrong.")

    r.h3("8.3.3  Provenance")
    r.para(
        "Every version writes a `_meta.json` sidecar recording the product, job and version "
        "identifiers, the provider and model, a per-node source map, the warnings raised and the "
        "content of every artefact. The review page reads it to show which model produced the version "
        "and which parts are unchanged; the next run reads it as the source for carry-forward.")
