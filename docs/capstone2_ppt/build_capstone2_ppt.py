"""Build the Capstone 2 PPT for AI-Powered Marketing Content Generation
by re-using the Sample PPT's theme/layouts and replacing content in place.
"""
import copy
import os
from pptx import Presentation
from pptx.util import Emu

HERE = os.path.dirname(os.path.abspath(__file__))
SRC = os.path.join(HERE, "Sample PPT.pptx")
OUT = os.path.join(HERE, "AI06_Shyam_Capstone2_PPT_v1.pptx")
FIG = os.path.join(HERE, "..", "capstone2_report", "figures")
REPORT_ASSETS = os.path.join(HERE, "..", "capstone2_report")


def set_lines(text_frame, lines):
    """Replace the text of a text_frame's paragraphs with `lines`,
    reusing the first paragraph/run's formatting as a template for all
    lines so font/color/bullet formatting from the sample deck survives."""
    paras = text_frame.paragraphs
    template_p = paras[0]
    # Remove all paragraphs after the first
    for p in paras[1:]:
        p._p.getparent().remove(p._p)

    def set_para_text(p, text):
        runs = p.runs
        if runs:
            runs[0].text = text
            for r in runs[1:]:
                r.text = ""
        else:
            p.text = text

    if not lines:
        set_para_text(template_p, "")
        return

    set_para_text(template_p, lines[0])
    txBody = template_p._p.getparent()
    for line in lines[1:]:
        new_p_elem = copy.deepcopy(template_p._p)
        txBody.append(new_p_elem)
        # find the pptx paragraph wrapper freshly and set its text
        from pptx.text.text import _Paragraph
        wrapped = _Paragraph(new_p_elem, text_frame)
        set_para_text(wrapped, line)


def remove_shape(slide, shape):
    """Remove a shape and drop any relationships it referenced. The shape
    element is detached from the tree before drop_rel is called, because
    drop_rel counts remaining references by scanning the live slide XML —
    a shape whose own XML repeats an rId (e.g. an OLE object's mc:Choice /
    mc:Fallback branches) would otherwise look "still referenced"."""
    import re
    xml = shape._element.xml
    rids = set(re.findall(r'r:\w+="(rId\d+)"', xml))
    shape._element.getparent().remove(shape._element)
    for rid in rids:
        try:
            slide.part.drop_rel(rid)
        except KeyError:
            pass


def get_shape(slide, name):
    for shape in slide.shapes:
        if shape.name == name:
            return shape
    raise KeyError(name)


def set_table(shape, rows):
    table = shape.table
    for r, row_vals in enumerate(rows):
        for c, val in enumerate(row_vals):
            cell = table.cell(r, c)
            tf = cell.text_frame
            set_lines(tf, [val])


def replace_picture(slide, shape_name, new_image_path, max_w=None, max_h=None):
    shape = get_shape(slide, shape_name)
    left, top, width, height = shape.left, shape.top, shape.width, shape.height
    box_w = max_w or width
    box_h = max_h or height
    remove_shape(slide, shape)
    pic = slide.shapes.add_picture(new_image_path, left, top)
    ratio = pic.width / pic.height
    box_ratio = box_w / box_h
    if ratio > box_ratio:
        pic.width = box_w
        pic.height = int(box_w / ratio)
    else:
        pic.height = box_h
        pic.width = int(box_h * ratio)
    pic.left = left + (box_w - pic.width) // 2
    pic.top = top + (box_h - pic.height) // 2
    return pic


def main():
    prs = Presentation(SRC)
    slides = prs.slides

    # ---- Slide 1: Cover ----
    s = slides[0]
    t = get_shape(s, "Title 1")
    t.text_frame.paragraphs[0].runs[0].text = "AI-Powered Marketing Content "
    t.text_frame.paragraphs[0].runs[1].text = "Generation"
    tb = get_shape(s, "TextBox 2")
    set_lines(tb.text_frame, [
        "M.Sc. in",
        "Artificial Intelligence",
        "Capstone Project 2 Presentation",
        "Year: II",
    ])
    for shape in s.shapes:
        if shape.name == "Title 1" and shape.shape_id != t.shape_id:
            set_lines(shape.text_frame, ["Shyam Sundar K", "SRN: R22MSA55 | Date: 22/08/2026"])

    # ---- Slide 3: Introduction ----
    s = slides[2]
    tbl = get_shape(s, "Table 2")
    set_table(tbl, [
        ["Background", "Current Status", "Why This Topic?"],
        [
            "Short-form vertical video is the default unit of consumer marketing on Reels/Shorts\n"
            "A small D2C Shopify retailer needs a script, caption, hashtags and video per product, per revision\n"
            "Generative AI can write fluent copy, but fluent is not the same as factually traceable",

            "LLM tools exist but are fragmented across copy, narration and video with nothing carrying facts through\n"
            "Brand governance (tone, banned words, compliance) is enforced by human review, not by generation\n"
            "Generative systems fall back to templates on failure, indistinguishable from real output",

            "Prevent hallucinated product claims (price, size, material) from reaching reviewers as if they were facts\n"
            "Make brand voice, compliance and visual rules machine-readable and enforced during generation\n"
            "Cut the marginal cost of content per SKU while keeping every claim traceable to its source",
        ],
        ["", "", ""],
    ])

    # ---- Slide 4: Literature Review ----
    s = slides[3]
    tbl = get_shape(s, "Table 102")
    set_table(tbl, [
        ["No.", "Title", "Author and Year", "Journal", "Description", "Insights", "Research Gaps/Comments"],
        ["1", "KOBE: Towards Knowledge-Based Personalized Product Description Generation",
         "Chen et al. (2019)", "KDD",
         "Transformer generating personalised product descriptions conditioned on aspects, user categories and a knowledge base.",
         "Catalogue attributes are a sufficient basis for usable copy.",
         "Trained model, retargeting means retraining; produces one artefact, not a campaign."],
        ["2", "Survey of Hallucination in Natural Language Generation",
         "Ji et al. (2023)", "ACM Computing Surveys",
         "Canonical taxonomy separating intrinsic hallucination (contradicts source) from extrinsic (unverifiable).",
         "Names the grounding failure precisely for marketing copy.",
         "Does not specify an enforcement mechanism during generation."],
        ["3", "On Faithfulness and Factuality in Abstractive Summarization",
         "Maynez et al. (2020)", "ACL",
         "Shows models hallucinate content unfaithful to the input at high rates; overlap metrics (ROUGE) do not detect it.",
         "Fluency scoring says nothing about whether facts are real.",
         "No structural mitigation proposed; motivates schema-level validation."],
        ["4", "LangGraph: Build Stateful Multi-Actor Applications with LLMs",
         "LangChain (2024)", "Framework Docs",
         "Compiled state graph with typed shared state and reducers for safe concurrent multi-agent writes.",
         "Enables a deterministic, bounded agent pipeline instead of an emergent conversation.",
         "General orchestration framework; not applied here to grounding or brand governance."],
    ])

    # ---- Slide 5: Problem Statement ----
    s = slides[4]
    tb = get_shape(s, "TextBox 3")
    set_lines(tb.text_frame, [
        "A small direct-to-consumer Shopify retailer must produce a script, caption, hashtag set and video "
        "for every product, variant and revision. Generative models can write this copy, but the failure that "
        "matters is not a clumsy sentence — it is a confident, brand-shaped claim about a specification or "
        "price that nobody can trace to a source, and that a reviewer may approve because it reads well.",
        "Key Challenges",
        "Tooling is fragmented across copy, narration and video, with nothing carrying product facts through all of them",
        "Brand governance is treated as review, not as a constraint enforced during generation",
        "Generative systems fall back to templates on failure — indistinguishable from real output at approval time",
        "No modelled path for scoped reviewer feedback; one objection forces a full regeneration",
    ])

    # ---- Slide 6: Objectives ----
    s = slides[5]
    tb = get_shape(s, "TextBox 2")
    set_lines(tb.text_frame, [
        "Design a brand-governed, multi-agent software architecture: LangGraph state graph, typed pipeline state and a provider-agnostic LLM gateway.",
        "Build the end-to-end generation pipeline: scraper, five prompt-driven LLM agents, a pluggable TTS chain and a deterministic video renderer.",
        "Implement the fact-grounding and validation layer: hardened JSON extraction, brand-derived schema validators, a repair-retry loop and a no-fallback rule.",
        "Test every functional requirement with an automated, offline test suite covering parsing, validation, persistence and pipeline logic.",
        "Validate the assembled system against a live product page: timing, audio/video sync, claim traceability and provenance.",
        "Deploy the system as a demo-ready application: Streamlit dashboard, review page, job queue and human approve/reject gate.",
    ])

    # ---- Slide 7: Methodology ----
    s = slides[6]
    tb = get_shape(s, "TextBox 10")
    set_lines(tb.text_frame, ["Workflow:"])
    tb12 = get_shape(s, "TextBox 12")
    set_lines(tb12.text_frame, [
        "Research Design",
        "",
        "Research Type: Design and Development Research",
        "",
        "System: Brand-Governed Multi-Agent Marketing Content Generator",
        "",
        "Input: Single public Shopify product URL",
        "",
        "Architecture: LangGraph + Streamlit + SQLite",
        "",
        "Execution: 9-node state graph across 7 supersteps, 5 LLM agents",
    ])
    # Replace the SmartArt/diagram placeholder with the TDSP figure if present
    for shape in list(s.shapes):
        if shape.name.startswith("Diagram"):
            left, top, width, height = shape.left, shape.top, shape.width, shape.height
            remove_shape(s, shape)
            fig = os.path.join(FIG, "fig_5_1_tdsp.png")
            if os.path.exists(fig):
                pic = s.shapes.add_picture(fig, left, top)
                ratio = pic.width / pic.height
                box_ratio = width / height
                if ratio > box_ratio:
                    pic.width = width
                    pic.height = int(width / ratio)
                else:
                    pic.height = height
                    pic.width = int(height * ratio)
                pic.left = left + (width - pic.width) // 2
                pic.top = top + (height - pic.height) // 2

    # ---- Slide 8: Resource Specification ----
    s = slides[7]
    tbl = get_shape(s, "Table 3")
    set_table(tbl, [
        ["Software", "Hardware", "Other Resources"],
        ["Python 3.9+", "Standard laptop CPU (no GPU)", "Shopify product JSON (public)"],
        ["LangGraph", "8+ GB RAM", "LLM API (OpenAI / Gemini / Anthropic)"],
        ["Streamlit + SQLite", "Sufficient SSD for versioned outputs", "ElevenLabs API (optional, for TTS)"],
        ["Pillow / MoviePy renderer", "Windows / Linux / macOS", "Piper TTS (offline fallback)"],
        ["pytest (174-test suite)", "", "Environment variables (.env)"],
    ])
    tb = get_shape(s, "TextBox 8")
    set_lines(tb.text_frame, [
        "Key Highlights",
        "No GPU required, runs on a standard laptop",
        "Provider-agnostic LLM gateway",
        "Every brand rule externalised into one YAML file",
        "Fully offline-testable, no API key needed for the suite",
    ])

    # ---- Slide 9: Software Design ----
    s = slides[8]
    tb = get_shape(s, "TextBox 10")
    set_lines(tb.text_frame, [
        "Design Highlights",
        "",
        "Nine-node LangGraph pipeline with a parallel fan-out superstep",
        "",
        "Hardened JSON extraction with brand-derived schema validation",
        "",
        "Repair-retry loop with a strict no-fallback rule",
        "",
        "Six-table relational model; a version exists only when complete",
        "",
        "Deterministic renderer retimed to the measured narration length",
    ])
    fig = os.path.join(FIG, "fig_7_1_architecture.png")
    if os.path.exists(fig):
        replace_picture(s, "Picture 2", fig)

    # ---- Slide 10: Implementation ----
    s = slides[9]
    tb = get_shape(s, "TextBox 3")
    set_lines(tb.text_frame, ["Implementation Deliverables"])
    items = [
        ("TextBox 12", "Scraper & Data Layer", "139-line Shopify scraper separating specs from prose; SQLite persistence is also the job queue."),
        ("TextBox 18", "Five LLM Agents", "Brief, script, caption, hashtag and shot-plan agents; three run in a parallel superstep with explicit reducers."),
        ("TextBox 24", "Fact Grounding & Validation", "Four-stage hardened JSON extractor, brand-derived validators and an error-fed repair-retry loop."),
        ("TextBox 30", "Speech & Video Rendering", "Pluggable TTS chain (ElevenLabs → Piper → pyttsx3) and a deterministic 1080×1920 H.264 renderer retimed to the narration."),
        ("TextBox 36", "Review Application", "Streamlit dashboard, worker, and human approve/reject gate with scoped feedback and dependency cascade."),
    ]
    for name, title, desc in items:
        tb = get_shape(s, name)
        set_lines(tb.text_frame, [title, desc])
    fig = os.path.join(FIG, "fig_7_2_dag.png")
    if os.path.exists(fig):
        replace_picture(s, "Picture 39", fig)

    # ---- Slide 11: Demo (screenshots) ----
    s = slides[10]
    fig_a = os.path.join(FIG, "fig_8_6_hitl.png")
    fig_b = os.path.join(FIG, "fig_9_4_contact_sheet.png")
    if os.path.exists(fig_a):
        replace_picture(s, "Picture 3", fig_a)
    if os.path.exists(fig_b):
        replace_picture(s, "Picture 8", fig_b)
    tb = get_shape(s, "TextBox 10")
    set_lines(tb.text_frame, ["Human-in-the-Loop Review & Regeneration Loop"])
    tb = get_shape(s, "TextBox 12")
    set_lines(tb.text_frame, ["Rendered Video Frames: Title, Feature x2, Specification and Call-to-Action Scenes"])

    # ---- Slide 12: Demo (repurposed as timing chain) ----
    s = slides[11]
    title = get_shape(s, "Title 7")
    set_lines(title.text_frame, ["Timing Chain & A/V Sync"])
    fig = os.path.join(FIG, "fig_9_3_av_sync.png")
    for shape in list(s.shapes):
        if shape.shape_type == 16 or "Demo_Dashboard" in shape.name:  # MEDIA
            left, top, width, height = shape.left, shape.top, shape.width, shape.height
            remove_shape(s, shape)
            if os.path.exists(fig):
                pic = s.shapes.add_picture(fig, left, top)
                ratio = pic.width / pic.height
                box_ratio = width / height
                if ratio > box_ratio:
                    pic.width = width
                    pic.height = int(width / ratio)
                else:
                    pic.height = height
                    pic.width = int(height * ratio)
                pic.left = left + (width - pic.width) // 2
                pic.top = top + (height - pic.height) // 2
    tb = get_shape(s, "TextBox 3")
    set_lines(tb.text_frame, [
        "Validator recomputes duration from word count (22.90s) -> Piper narration measured from WAV header "
        "(22.37s) -> all five scenes rescaled by ~0.978 -> encoded MP4 reports 22.37s.",
    ])

    # ---- Slide 13: Testing, Validation and Results ----
    s = slides[12]
    tbl = get_shape(s, "Table 2")
    set_table(tbl, [
        ["Test Scenario", "Expected Outcome", "Status"],
        ["Duplicate product URL", "Surfaced as already-exists; no second row created", "Pass"],
        ["Script duration inflated by model", "Duration recomputed from word count, not model estimate", "Pass"],
        ["TTS engine failure", "No partial WAV written; falls back to next engine in chain", "Pass"],
        ["Caption exceeds limit after 3 attempts", "Job fails; no version or placeholder created", "Pass"],
        ["Live end-to-end product run", "8 artefacts produced; narration and MP4 duration matched exactly", "Pass"],
    ])
    tb = get_shape(s, "TextBox 9")
    set_lines(tb.text_frame, [
        "Key Results",
        "174 automated tests, 171 passed (98.3%), running offline in 5 seconds with no API key",
        "Live run: 8 artefacts from one URL in 214 seconds; every claim traced to the scraped record",
        "Rendered video duration (22.37s) matched the measured narration exactly",
        "System failed 4 of 5 recorded jobs without ever showing a reviewer content it had not really generated",
    ])

    # ---- Slide 14: Conclusion and Future Scope ----
    s = slides[13]
    tb = get_shape(s, "TextBox 3")
    set_lines(tb.text_frame, [
        "Conclusion",
        "A generative system can produce a complete, reviewable marketing package without inventing product claims, provided it is willing to fail.",
        "All 6 objectives addressed: 5 fully met, 1 partially met (test-fixture issue, not a production defect).",
        "Brand-as-data governance: one YAML file drives prompts, validation limits and rendered visuals.",
        "No-fallback architecture: absence of placeholder content is a structural property, asserted by a named test.",
        "Future Scope",
        "A claim-verification node cross-checking every number against the specification dictionary",
        "A brand-compliance critique pass in the manner of Self-Refine",
        "Multi-worker operation via atomic job-claiming",
        "Direct publishing across all aspect ratios; an LLM-judge evaluation study",
    ])

    # ---- Slide 15 & 16: References ----
    s = slides[14]
    tb = get_shape(s, "TextBox 3")
    set_lines(tb.text_frame, [
        "Z. Ji et al., “Survey of Hallucination in Natural Language Generation,” ACM Computing Surveys, 2023.",
        "J. Maynez, S. Narayan, B. Mirylenka, R. McDonald, “On Faithfulness and Factuality in Abstractive Summarization,” ACL, 2020.",
        "H. Chen et al., “KOBE: Towards Knowledge-Based Personalized Product Description Generation,” KDD, 2019.",
        "H. Rashkin et al., “Measuring Attribution in Natural Language Generation Models,” 2021.",
        "Y. Shen, C. Wu, “ReAct: Synergizing Reasoning and Acting in Language Models,” 2023.",
        "Q. Wu et al., “AutoGen: Enabling Next-Gen LLM Applications via Multi-Agent Conversation,” 2023.",
    ])

    s = slides[15]
    tb = get_shape(s, "TextBox 3")
    set_lines(tb.text_frame, [
        "LangChain, “LangGraph: Build Stateful Multi-Actor Applications with LLMs,” https://langchain-ai.github.io/langgraph/.",
        "B. J. Willard, R. Louf, “Efficient Guided Generation for Large Language Models,” 2023.",
        "A. Blattmann et al., “Stable Video Diffusion,” 2023. [Online].",
        "“Team Data Science Process,” Microsoft, https://learn.microsoft.com/azure/architecture/data-science-process-overview/.",
        "Shopify, “The Product JSON Endpoint,” Shopify Developer Documentation.",
        "ASCI, “Code for Self-Regulation of Advertising Content in India,” Advertising Standards Council of India.",
    ])

    # ---- Slide 17: Annexure ----
    s = slides[16]
    tb = get_shape(s, "TextBox 8")
    set_lines(tb.text_frame, ["Similarity Index"])
    tb = get_shape(s, "TextBox 16")
    set_lines(tb.text_frame, ["Code Snippet: Repair-Retry Loop"])
    fig_snippet = os.path.join(REPORT_ASSETS, "code_snippet_2_repair_retry_loop.png")
    if os.path.exists(fig_snippet):
        replace_picture(s, "Picture 14", fig_snippet)
    # Picture 3 was the sample project's own similarity-index screenshot;
    # this project's Turnitin scan is still pending (see report Appendix B),
    # so drop the picture and note it as pending instead of showing a
    # screenshot that belongs to a different project.
    pic3 = get_shape(s, "Picture 3")
    left, top, width, height = pic3.left, pic3.top, pic3.width, pic3.height
    remove_shape(s, pic3)
    from pptx.util import Pt
    note_box = s.shapes.add_textbox(left, top, width, height)
    note_tf = note_box.text_frame
    note_tf.text = "Turnitin similarity report pending — to be inserted (see report Appendix B)."
    note_tf.paragraphs[0].runs[0].font.size = Pt(16)
    note_tf.paragraphs[0].runs[0].font.italic = True
    # Remove the leftover embedded OLE object from the sample deck
    for shape in list(s.shapes):
        if shape.shape_type == 7:  # EMBEDDED_OLE_OBJECT
            remove_shape(s, shape)

    # ---- Slide 18: GitHub Link ----
    s = slides[17]
    tb = get_shape(s, "TextBox 3")
    set_lines(tb.text_frame, [
        "https://github.com/Shyamsundarkanaka/AI-Powered-Marketing-Content-Generation",
    ])

    prs.save(OUT)
    print("Saved:", OUT)


if __name__ == "__main__":
    main()
