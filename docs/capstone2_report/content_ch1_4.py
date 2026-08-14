"""Chapters 1-4: Introduction, Literature Review, Problem Statement, Objectives."""


def ch1(r):
    r.h1("Chapter 1: Introduction")

    r.h2("1.1  Background Information")
    r.para(
        "Short-form vertical video has become the default unit of consumer marketing. A brand selling "
        "through Instagram Reels or YouTube Shorts does not publish one campaign a quarter; it "
        "publishes a clip per product, per variant, per seasonal angle, and revises those clips "
        "whenever a reviewer disagrees with the hook. Each clip needs a strategy note, a script "
        "written to be spoken, a caption written to survive truncation, a hashtag set, a narration "
        "and an edit.")
    r.para(
        "Huang and Rust distinguish mechanical AI that automates repetitive marketing tasks, thinking "
        "AI that turns data into decisions, and feeling AI that handles interaction [1]. Generative "
        "work long sat outside all three, because models could produce fluent copy but not copy an "
        "organisation would put its name on. Grewal et al. argue that generative AI is now reshaping "
        "content creation, while stressing that the human augmentation an output requires decides "
        "whether the technology is usable at all [2]. E-commerce fits this well because the source "
        "facts are already structured [3].")
    r.para(
        "That failure mode is hallucination: text that is fluent, plausible and unsupported by the "
        "source [4]. In a chatbot it is an annoyance. In a marketing asset it is a claim — “45 cm "
        "tall”, “hand-finished”, “₹19,999” — that reads exactly like the true claims around it, may "
        "be approved by a reviewer with no easy way to check it, and then goes out under the "
        "brand's name.")
    r.fig("fig_1_1_scope.png",
          "Fig. 1.1: Scope of the system — one public Shopify product URL in, eight versioned "
          "artefacts out, with a human review gate in between.", width_in=3.0)

    r.h2("1.2  Need for the Study")
    r.para(
        "Three gaps motivate this work. **Tooling is fragmented:** copy comes from one tool, "
        "narration from a second, an edit from a third, and nothing carries the product's "
        "specification table through all of them, so nothing guarantees that the number spoken in "
        "the narration is the number printed on the frame.")
    r.para(
        "**Brand governance is treated as review rather than as constraint.** Tone of voice, banned "
        "vocabulary, persona targeting and regulatory language usually live in a document someone is "
        "expected to have read. Nothing in the generation path enforces them, so every violation must "
        "be caught downstream by the reviewer who is already the bottleneck. Under advertising codes "
        "such as the ASCI Code, which requires advertisements to be truthful and places the "
        "substantiation burden on the advertiser [26], that is a weak control.")
    r.para(
        "**Generative systems in this space are built to always return something.** When a model "
        "fails they fall back to a template or a cached response, which is defensible for a search "
        "box and indefensible for marketing copy, because the fallback is indistinguishable from real "
        "output at the point where a human approves it. A system that produces marketing claims needs "
        "the opposite default: if it cannot produce something grounded and valid, it should produce "
        "nothing and say why.")

    r.h2("1.3  Scope and Potential Impact")
    r.para(
        "The system takes a single public Shopify product URL and produces a complete, reviewable "
        "package for one short-form vertical video. As Fig. 1.1 shows, that package is eight "
        "artefacts: a campaign brief, a five-beat voiceover script, an Instagram/Reels caption, a "
        "hashtag set, a shot-by-shot video plan, a narration WAV, a rendered 1080×1920 H.264 MP4 and "
        "a provenance sidecar. The brand throughout is a small direct-to-consumer Shopify retailer — "
        "the pipeline is agnostic to what it sells, whether gifts, apparel, handmade goods or any "
        "other catalogue of physical products. "
        "Out of scope are publishing, engagement measurement, generative video or image synthesis, "
        "multi-tenant hosting and any language other than English.")
    r.para(
        "For a catalogue retailer the marginal cost of a product's first content package drops from a "
        "multi-person workflow to a click and a review; the measured end-to-end run completed in "
        "214 seconds on a laptop. The less obvious impact is on trust, because every artefact carries "
        "a provenance record naming the model that produced it. The approach generalises to any "
        "domain where the source facts are structured and the copy must not exceed them.")


def ch2(r):
    r.h1("Chapter 2: Literature Review")
    r.para(
        "This chapter reviews the work this project builds on, positioning each contribution and "
        "stating what remains unresolved. Section 2.6 consolidates the gap the project addresses.")

    r.h2("2.1  Generative AI in Marketing Content Production")
    r.para(
        "Huang and Rust's three-stage framework remains the clearest account of where automation sits "
        "in a marketing function [1]; its value here is that it names content production as "
        "mechanical work worth automating while leaving open how quality is controlled. Grewal et al. "
        "observe that the cases which work keep a human on the output rather than only on the prompt "
        "[2]. Neither specifies a mechanism by which brand voice or factual constraints are enforced "
        "during generation, and neither treats model failure as an engineering event with a defined "
        "outcome.")

    r.h2("2.2  Generation from Structured E-Commerce Product Data")
    r.para(
        "Chen et al. proposed KOBE, a Transformer generating personalised product descriptions by "
        "conditioning on product aspects, user categories and a knowledge base [3]. It establishes "
        "that catalogue attributes are a sufficient basis for usable copy, but KOBE is a trained "
        "model, so retargeting means retraining, and its output is one artefact rather than a "
        "campaign. This project supplies the catalogue to a general-purpose model at inference time "
        "and generates five interdependent artefacts whose consistency the pipeline enforces, "
        "exploiting the fact that a Shopify product page's `.json` representation is publicly "
        "readable [5].")

    r.h2("2.3  Hallucination, Faithfulness and Attribution")
    r.para(
        "Ji et al. give the canonical taxonomy, separating intrinsic hallucination, where output "
        "contradicts the source, from extrinsic hallucination, where output cannot be verified "
        "against it [4]. Huang et al. conclude that no single technique eliminates hallucination and "
        "practical systems must layer several [6]. Maynez et al. supply the result that matters most "
        "here: models hallucinate content unfaithful to the input at high rates, and overlap metrics "
        "such as ROUGE do not detect it [7], so a caption scoring well on fluency says nothing about "
        "whether its numbers are real.")
    r.para(
        "Rashkin et al. define Attributable to Identified Sources, a framework in which every claim "
        "about the external world must be verifiable against an identified source [8]. The dominant "
        "mitigation in practice is retrieval augmentation [9], which assumes a large corpus that must "
        "be searched. Here there is exactly one relevant document per product and it is known before "
        "generation begins, so the retrieval problem disappears and what remains is the harder "
        "problem of ensuring the model does not exceed a source it has already been given.")

    r.h2("2.4  Structured Output and Multi-Agent Orchestration")
    r.para(
        "Willard and Louf reformulate constrained generation as transitions in a finite-state machine "
        "over the model's vocabulary [10], and Geng et al. reach a similar guarantee through "
        "grammar-constrained decoding [11]. Both require access to the token distribution, an "
        "assumption that fails for hosted commercial APIs, which is the case here and the common case "
        "in industry. The practical alternative is post-hoc: parse defensively, validate against a "
        "schema, re-ask with the violation quoted. Liu et al.'s survey supplies the other half of the "
        "problem, that the prompt is where task knowledge is injected [12].")
    r.para(
        "On orchestration, ReAct shows that explicit decomposition improves accuracy and "
        "interpretability [13]; AutoGen generalises this to conversable agents [14]; and Guo et al. "
        "identify coordination, state management and evaluation as open problems [15]. Conversational "
        "frameworks are non-deterministic: the agents decide who speaks next, so the number of model "
        "calls is emergent, which for a pipeline whose cost per run is a billing line is the wrong "
        "trade. LangGraph offers a compiled state graph with typed shared state and reducers that "
        "make concurrent writes safe [16]. Self-Refine shows a model can critique its own output "
        "[17]; the loop here takes its critique from a deterministic validator instead, giving a "
        "bounded loop that cannot talk itself into accepting bad output.")

    r.h2("2.5  Media Generation and Human Oversight")
    r.para(
        "Blattmann et al.'s Stable Video Diffusion establishes a training recipe for latent video "
        "diffusion [18]. For a product marketing asset, synthesised video is nonetheless the wrong "
        "tool, for a reason unrelated to quality: a diffusion model asked to depict a specific "
        "product produces a plausible-looking one, not that one. The correct problem is "
        "animating authoritative stills. This project implements the classical 2D form of the Ken "
        "Burns effect [19], because the goal is a deterministic renderer that runs on a laptop CPU, "
        "and takes narration from a pluggable chain led by a hosted neural voice, falling back to "
        "Piper, which packages VITS-derived voices [20] as ONNX models that run offline [21].")
    r.para(
        "Wu et al. observe that most human-in-the-loop work targets improving model performance "
        "rather than governing model output in production [22]. Amershi et al.'s guidelines address "
        "the second concern directly: make clear what the system can do and why it did what it did, "
        "and support efficient correction [23]. Sculley et al.'s warning that configuration and "
        "undeclared consumers are where technical debt accumulates around a model [24] is answered "
        "here by fail-fast typed configuration, a brand file with a validated required-key set, and a "
        "provenance record naming every consumer of an artefact.")

    r.h2("2.6  Comparative Summary and Research Gap")
    r.para(
        "Table 2.1 places the reviewed work against the four properties a system of this kind "
        "needs: grounding in a verifiable source, machine-enforced brand governance, coverage of "
        "the complete artefact set, and a defined behaviour when generation fails.")
    r.tbl(
        "Table 2.1: Reviewed approaches against the four requirements of the problem",
        ["Approach", "Grounded in a verifiable source", "Machine-enforced brand rules",
         "Complete artefact set", "Defined failure behaviour"],
        [
            ["AI-in-marketing frameworks [1], [2]", "Not addressed", "Not addressed",
             "Conceptual only", "Not addressed"],
            ["Trained product-description generation [3]",
             "Yes — catalogue attributes", "Implicit in training data",
             "One artefact", "Not addressed"],
            ["Retrieval-augmented generation [9]", "Yes — retrieved documents", "No",
             "Task-dependent", "Degrades to unretrieved generation"],
            ["Constrained decoding [10], [11]", "No — shape only",
             "Shape only", "Not applicable", "Shape guaranteed, content not"],
            ["Conversational multi-agent [14], [15]", "Tool-dependent", "No",
             "Possible but emergent", "Unbounded; termination emergent"],
            ["Generative video [18]", "No — synthesises the product", "No", "Video only",
             "Not addressed"],
            ["**This project**", "**Yes — the scraped record is the only permitted fact source**",
             "**Yes — one brand file drives prompts, validators and renderer**",
             "**Eight artefacts, consistency enforced by graph dependencies**",
             "**Fail the run; never substitute placeholder copy**"],
        ],
        widths=[2.3, 2.1, 1.9, 1.9, 2.1], size=8.5, header_size=8.5)
    r.para("Four gaps follow, and they are what this project is built to close.")
    r.numbered([
        "Grounding is studied as a retrieval or evaluation problem, not as an engineering "
        "constraint on a pipeline where the source document is already known.",
        "Brand governance is treated as human review rather than as machine-readable configuration "
        "driving both the prompt and the validator.",
        "Published systems generate one artefact; nothing addresses the consistency problem when a "
        "brief, script, caption, hashtag set and shot plan must all agree about the same product.",
        "Failure behaviour is almost never specified, and scoped feedback — “this part is wrong, "
        "the rest is fine” — is not modelled, so one objection costs a full regeneration.",
    ])
    r.para(
        "Liu et al.'s G-Eval shows a strong model can score generated text in reasonable agreement "
        "with human judgement [25], but it was not adopted here because an LLM judge assesses "
        "quality, whereas the property this system guarantees is groundedness.")


def ch3(r):
    r.h1("Chapter 3: Problem Statement")

    r.h2("3.1  Setting, Context and Stakeholders")
    r.para(
        "A small direct-to-consumer retailer of this kind — selling gifts, apparel, handmade goods "
        "or any other catalogue of physical products — operates through a Shopify storefront. Each "
        "product page carries a photographic set, a descriptive body and an HTML specification "
        "table listing whatever attributes the catalogue defines, such as size, material, weight or "
        "other measurable figures.")
    r.para(
        "Discovery for this category happens on Instagram and YouTube rather than on the storefront, "
        "so a product without a vertical clip is invisible to the audience most likely to buy it. The "
        "content requirement is therefore not campaign-shaped but catalogue-shaped: it scales with "
        "the number of SKUs rather than with the marketing calendar, and every step of the manual "
        "chain repeats in full whenever a reviewer objects to any single element.")
    r.tbl("Table 3.1: Stakeholder map",
          ["Stakeholder", "Position in the process", "Interest and concern"],
          [
              ["Marketing reviewer", "Approves or rejects every asset before publication",
               "Wants a publishable clip quickly and needs to see at a glance what changed between "
               "versions. Is the bottleneck today, and is the person a confident hallucination "
               "would deceive."],
              ["Brand owner", "Defines voice, positioning and permissible claims",
               "Wants tone and banned vocabulary applied consistently across hundreds of assets "
               "without personally reading each one."],
              ["Product / catalogue team", "Maintains the product pages and specification tables",
               "Is the authoritative source of every fact the marketing may state; needs generated "
               "copy to track the page when a specification is corrected."],
              ["Compliance reviewer", "Checks claims against the ASCI Code [26]",
               "Needs each numeric claim traceable to a source and manufacturer-claim disclosures "
               "present wherever a headline figure is the main claim."],
              ["Engineering / operations", "Runs the system",
               "Needs reproducible runs, diagnosable failures, swappable model providers and "
               "predictable cost per run."],
          ], widths=[1.8, 2.4, 5.8], size=9.5)

    r.h2("3.2  Strategic Significance")
    r.para(
        "**It is a cost problem with a compounding shape.** The manual chain costs roughly the same "
        "for the tenth product as for the first, and a revision costs nearly as much as an "
        "original, so a retailer cannot expand its catalogue without linearly expanding its "
        "marketing team.")
    r.para(
        "**It is a risk problem with an asymmetric payoff.** A clumsy sentence costs engagement; an "
        "invented specification costs credibility and, under the ASCI Code, exposes the advertiser "
        "to a substantiation challenge [26]. Because a hallucinated claim is stylistically "
        "indistinguishable from a true one, the risk rises with output volume rather than falling, "
        "since review attention per asset falls.")
    r.para(
        "**It is a governance problem that is currently unmodelled.** Brand voice exists as prose "
        "in a document, and nothing connects that document to what a generation system does. Until "
        "the rules are machine-readable, every rule change requires re-educating humans rather than "
        "editing a file.")

    r.h2("3.3  Statement of the Problem")
    r.quote(
        "Given a single public product URL from a Shopify storefront, produce a complete and "
        "internally consistent short-form video marketing package — campaign brief, spoken script, "
        "caption, hashtag set, shot plan, narration and rendered vertical video — such that every "
        "factual claim traces to the scraped product record, every element conforms to a "
        "machine-readable brand definition, the package is presented to a human for approval with "
        "its provenance visible, a rejection carries scoped feedback into the next version without "
        "regenerating what the reviewer accepted, and the system fails visibly rather than "
        "substituting plausible placeholder content when it cannot meet those conditions.")
    r.para(
        "The last clause is what shapes the architecture. It rules out every convenience that would "
        "let an unverified string reach a reviewer, and its consequences run through the design and "
        "the implementation that follow.")


def ch4(r):
    r.h1("Chapter 4: Objectives of the Study")
    r.para(
        "Six objectives define the study. Each names its execution phase, states what will be "
        "produced, and is written so that its achievement can be checked against something "
        "observable. Section 4.7 maps every objective to the chapter that demonstrates it.")

    r.h2("4.1  Objective 1 — Design")
    r.para(
        "**Design a brand-governed, multi-agent software architecture** converting a single public "
        "Shopify product URL into a complete short-form video marketing package. The design must "
        "specify the LangGraph state-graph topology and the point at which independent agents may "
        "run concurrently; the typed pipeline state and the reducers that make those concurrent "
        "writes safe; a six-table relational model in which a version exists only when every "
        "artefact behind it is on disk; and a provider-agnostic gateway through which the system "
        "reaches OpenAI, Gemini or Anthropic without any node knowing which is active.")

    r.h2("4.2  Objective 2 — Build")
    r.para(
        "**Build the end-to-end generation pipeline:** a Shopify scraper that extracts the "
        "specification table separately from the descriptive prose; a persistence layer that is also "
        "the job queue; five prompt-driven LLM agents producing the brief, script, caption, hashtags "
        "and shot plan; a pluggable text-to-speech chain led by a hosted engine with local offline "
        "fallbacks; and a deterministic renderer "
        "composing a 1080×1920 H.264 video whose duration matches the synthesised narration exactly. "
        "Every brand rule must live in a single machine-readable file and nowhere in the Python.")

    r.h2("4.3  Objective 3 — Build")
    r.para(
        "**Implement the fact-grounding and validation layer** that makes an unsupported claim "
        "structurally difficult to produce and impossible to publish silently: a hard-fact rule "
        "binding every agent to the scraped record; a four-stage hardened JSON extractor; "
        "brand-derived schema validators with an explicit split between problems the code may "
        "normalise and problems only the model can fix; a repair-retry loop returning the specific "
        "violation to the model; and a no-fallback rule under which a run that cannot produce valid "
        "content fails rather than substituting placeholder copy.")

    r.h2("4.4  Objective 4 — Test")
    r.para(
        "**Test every functional requirement** through an automated suite executing offline, with no "
        "API key and no network access, covering response parsing against real-world malformations, "
        "every validator's accept, normalise and reject paths, scraper behaviour, repository and "
        "job-lifecycle semantics against a real temporary database, pipeline scoping and timing "
        "logic, and both interface pages. Results are to be recorded as executed test cases with "
        "outcomes, including any failures.")

    r.h2("4.5  Objective 5 — Validate")
    r.para(
        "**Validate the assembled system against a live product page**, measuring "
        "stage-level wall-clock latency across the complete job; the behaviour of the schema-retry "
        "mechanism when the model returns structurally wrong output; the correspondence between "
        "the computed script duration, the measured narration length and the rendered video "
        "duration; the completeness and provenance of the artefact set; and the fidelity of the "
        "rendered frames to the agent's shot plan.")

    r.h2("4.6  Objective 6 — Deploy")
    r.para(
        "**Deploy the system as a demo-ready application** runnable with a single command: a "
        "Streamlit dashboard and review page, a worker running either on a background thread or as "
        "its own process, a SQLite-backed FIFO job queue, immutable per-version output directories, "
        "and a human approve/reject gate in which a rejection carries written feedback and an "
        "explicit scope so out-of-scope content is carried forward byte-identically.")

    r.h2("4.7  Chapter Mapping")
    r.tbl("Table 4.1: Objective-to-chapter mapping",
          ["Objective", "Phase", "Addressed in", "What is demonstrated"],
          [
              ["Objective 1", "Design", "Chapter 7",
               "Layered architecture, LangGraph topology and superstep structure, ER model, "
               "data-flow diagram, request sequence, brand-as-data dependency map (Figs. 7.1–7.6)"],
              ["Objective 2", "Build", "Chapter 8, §8.1",
               "Scraper, data layer, five agents, prompt construction, speech chain and renderer, "
               "with annotated code excerpts and the GitHub repository link"],
              ["Objective 3", "Build", "Chapter 8, §8.2",
               "Hardened JSON extraction, normalise-versus-reject validation, repair-retry loop, "
               "no-fallback rule (Fig. 8.1, Tables 8.2–8.3)"],
              ["Objective 4", "Test", "Chapter 9, §9.2–§9.4",
               "174-test offline suite by area, executed functional test cases with outcomes, and "
               "an account of three failing tests (Tables 9.1–9.2, Fig. 9.1)"],
              ["Objective 5", "Validate", "Chapter 9, §9.5–§9.7; Chapter 10",
               "Five-job run ledger, stage-level timing, timing-chain verification, artefact "
               "inventory, claim traceability and real rendered frames (Tables 9.3–9.4, "
               "Figs. 9.2–9.4)"],
              ["Objective 6", "Deploy", "Chapter 8, §8.3; Chapter 9, §9.7",
               "Worker and queue, review application, scoped-feedback regeneration and cascade, "
               "provenance display, demonstration script (Fig. 8.2)"],
          ], widths=[1.0, 0.8, 1.5, 5.7], size=9.5)
