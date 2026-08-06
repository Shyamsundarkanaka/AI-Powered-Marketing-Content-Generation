"""Prompt construction for every agent in the pipeline.

Two things are true of every prompt here:

* The brand block from `brand.yaml` is injected verbatim. Editing the brand
  definition changes agent behaviour with no code change.
* The scraped product row is the *only* source of product facts. The agents are
  told this explicitly, because the failure mode that matters most in generated
  marketing copy is a confident invented number.

Each builder returns `(system, user)` and ends with a `# JSON KEYS` block
describing the shape it wants. The matching validator lives in
`graph/schemas.py` — when you change the keys here, change it there too, since
a response the prompt asks for but the validator rejects would loop until the
attempt budget runs out.
"""
from __future__ import annotations

import json
from typing import Any

from brand.loader import load_brand

MAX_DESCRIPTION_CHARS = 1800

JSON_CONTRACT = (
    "Reply with a single JSON object and nothing else. No prose before or after, "
    "no markdown fence. Use the exact keys described; do not add keys."
)


def _agent_system(role: str) -> str:
    brand = load_brand()
    return (
        f"{role}\n\n"
        f"You work inside {brand.name}'s marketing content pipeline. The brand "
        f"definition below is authoritative — follow it exactly, including the "
        f"banned vocabulary and the compliance rules.\n\n"
        f"{brand.prompt_block()}\n\n"
        "# HARD RULE ON FACTS\n"
        "The scraped product data in the user message is your only source of "
        "product facts. Never state a price, spec, range, speed, warranty, "
        "delivery time or discount that is not present there. If a fact you want "
        "is missing, write around it — do not estimate it.\n\n"
        f"# OUTPUT\n{JSON_CONTRACT}"
    )


def product_context(product: dict[str, Any], scraped: dict[str, Any]) -> str:
    """The scraped row, rendered for a prompt.

    Images are listed by index because the video-plan agent references them
    positionally and the renderer resolves those indices back to URLs.
    """
    brand = load_brand()
    price = scraped.get("price")
    compare_at = scraped.get("compare_at_price")
    specs = scraped.get("specs") or {}
    images = scraped.get("image_urls") or []
    description = (scraped.get("description_text") or "")[:MAX_DESCRIPTION_CHARS]

    lines = [
        "# SCRAPED PRODUCT DATA (the only facts you may use)",
        f"name: {scraped.get('title') or product.get('name')}",
        f"url: {product.get('url')}",
        f"price: {brand.currency_symbol}{price:,.0f}" if price else "price: not available",
    ]
    if compare_at:
        lines.append(f"compare_at_price: {brand.currency_symbol}{compare_at:,.0f}")
    lines.append(f"description: {description or 'not available'}")

    if specs:
        lines.append("specs:")
        lines.extend(f"  - {key}: {value}" for key, value in specs.items())
    else:
        lines.append("specs: none scraped")

    lines.append(f"images: {len(images)} available, referenced by index 0..{max(len(images) - 1, 0)}")
    lines.extend(f"  [{i}] {url}" for i, url in enumerate(images[:12]))
    return "\n".join(lines)


def revision_directive(revision: dict[str, Any] | None) -> str:
    """Reviewer feedback from a rejected version, as an explicit rewrite brief.

    This is the whole reason rejection is useful: without this block the next
    version regenerates the same copy and gets rejected for the same reason.
    """
    if not revision:
        return ""
    previous = json.dumps(revision.get("previous", {}), indent=2, ensure_ascii=False)
    return (
        "\n\n# REVISION REQUIRED\n"
        "A human reviewer rejected the previous version of this content. Their "
        "feedback is the primary instruction for this attempt — address it "
        "directly and visibly. Do not simply reword the previous output.\n\n"
        f"reviewer_feedback: {revision.get('feedback') or '(no written feedback given)'}\n\n"
        f"previous_version_output:\n{previous}"
    )


# --- Campaign brief ----------------------------------------------------------



def _persona_block(brand) -> str:
    """Render each persona's id/wants/fears so the model can match a product to a
    person by reasoning, instead of a hardcoded per-category rule living in code.
    """
    lines = []
    for p in brand.personas:
        wants = ", ".join(p.get("wants", []))
        fears = ", ".join(p.get("fears", []))
        lines.append(f"- {p['id']}: wants [{wants}]; fears [{fears}]")
    return "\n".join(lines)


def campaign_brief_prompt(state: dict[str, Any]) -> tuple[str, str]:
    brand = load_brand()
    persona_ids = [p["id"] for p in brand.personas]
    rules = brand.content_rules["campaign_brief"]
    system = _agent_system(
        "You are a senior performance marketing strategist. You write short, "
        "decision-ready campaign briefs that a creative team can act on without "
        "asking follow-up questions."
    )
    user = (
        f"{product_context(state['product'], state['scraped'])}\n\n"
        "# TASK\n"
        "Write the campaign brief for a single short-form social video promoting "
        "this product.\n\n"
        f"Choose exactly one target persona from: {', '.join(persona_ids)}. Base the "
        "choice on which persona's wants and fears best fit this specific product's "
        f"price, category and features:\n{_persona_block(brand)}\n\n"
        f"Provide at least {rules['proof_points_min']} proof points. Each proof point "
        "must quote or paraphrase a specific scraped spec, the price, or a line of "
        "the description — and name which one in `source`.\n\n"
        "# JSON KEYS\n"
        '{"objective": str, "target_persona": str (persona id), '
        '"persona_rationale": str (one sentence), "key_message": str (one sentence), '
        '"proof_points": [{"claim": str, "source": str}], '
        '"channels": [str], "success_metric": str}'
        f"{revision_directive(state.get('revision'))}"
    )
    return system, user


# --- Script ------------------------------------------------------------------


def script_prompt(state: dict[str, Any]) -> tuple[str, str]:
    brand = load_brand()
    rules = brand.content_rules["script"]
    low, high = rules["duration_seconds"]
    system = _agent_system(
        "You are a short-form video copywriter. You write voiceover scripts that "
        "are meant to be spoken aloud — every line must be sayable in one breath."
    )
    user = (
        f"{product_context(state['product'], state['scraped'])}\n\n"
        f"# APPROVED CAMPAIGN BRIEF\n{json.dumps(state['campaign_brief'], indent=2, ensure_ascii=False)}\n\n"
        "# TASK\n"
        f"Write the voiceover script. Total spoken length must land between {low} and "
        f"{high} seconds at roughly {rules['words_per_second']} words per second.\n\n"
        f"Use exactly these five beats in order: {', '.join(rules['structure'])}. "
        f"The hook beat is {rules['hook_max_words']} words or fewer and must work with "
        "the sound off.\n\n"
        "`line` is spoken word-for-word — no stage directions, no camera notes, no "
        "emoji, no bracketed asides. Put anything visual in `on_screen`, which is a "
        "short label the video renderer may burn onto the frame (max 6 words).\n\n"
        "# JSON KEYS\n"
        '{"title": str, "beats": [{"beat": str (one of the five), "line": str, '
        '"on_screen": str}], "estimated_duration_seconds": number}'
        f"{revision_directive(state.get('revision'))}"
    )
    return system, user


# --- Caption -----------------------------------------------------------------


def caption_prompt(state: dict[str, Any]) -> tuple[str, str]:
    brand = load_brand()
    rules = brand.content_rules["caption"]
    system = _agent_system(
        "You are a social copywriter. You write captions that sound like a person "
        "typed them, not like a brand approved them."
    )
    user = (
        f"{product_context(state['product'], state['scraped'])}\n\n"
        f"# CAMPAIGN BRIEF\n{json.dumps(state['campaign_brief'], indent=2, ensure_ascii=False)}\n\n"
        f"# SCRIPT\n{json.dumps(state['script'], indent=2, ensure_ascii=False)}\n\n"
        "# TASK\n"
        f"Write the Instagram/Reels caption. Maximum {rules['max_chars']} characters "
        f"total. The first line is at most {rules['first_line_max_chars']} characters "
        "and must stand on its own, because that is all most people see before the "
        "'more' truncation.\n\n"
        f"A call to action is required. Emoji: {brand.raw['language']['emoji']['caption']}. "
        "Do not put hashtags in the caption — they are generated separately.\n\n"
        "# JSON KEYS\n"
        '{"caption": str (full caption incl. the first line), "first_line": str, '
        '"cta": str, "char_count": number}'
        f"{revision_directive(state.get('revision'))}"
    )
    return system, user


# --- Hashtags ----------------------------------------------------------------


def hashtags_prompt(state: dict[str, Any]) -> tuple[str, str]:
    brand = load_brand()
    rules = brand.content_rules["hashtags"]
    low, high = rules["count"]
    system = _agent_system(
        "You are a social strategist choosing hashtags for reach without looking "
        "desperate."
    )
    user = (
        f"{product_context(state['product'], state['scraped'])}\n\n"
        f"# CAMPAIGN BRIEF\n{json.dumps(state['campaign_brief'], indent=2, ensure_ascii=False)}\n\n"
        "# TASK\n"
        f"Choose {low} to {high} hashtags. All lowercase. Always include "
        f"{', '.join(rules['always_include'])}. Never include any of: "
        f"{', '.join(rules['banned'])}.\n\n"
        "Mix three tiers: brand/product tags, category tags (personal electric "
        "mobility), and audience/intent tags. Keep them plausible for the Indian "
        "market.\n\n"
        "# JSON KEYS\n"
        '{"hashtags": [str, each starting with #], "rationale": str (one sentence)}'
        f"{revision_directive(state.get('revision'))}"
    )
    return system, user


# --- Video plan --------------------------------------------------------------


def video_plan_prompt(state: dict[str, Any]) -> tuple[str, str]:
    brand = load_brand()
    rules = brand.content_rules["video_plan"]
    video = brand.video
    low, high = rules["scene_count"]
    image_count = len(state["scraped"].get("image_urls") or [])
    system = _agent_system(
        "You are a short-form video director. You plan shot-by-shot for a vertical "
        "video assembled from existing product photography — there is no footage, "
        "only stills with camera movement applied."
    )
    user = (
        f"{product_context(state['product'], state['scraped'])}\n\n"
        f"# SCRIPT\n{json.dumps(state['script'], indent=2, ensure_ascii=False)}\n\n"
        "# TASK\n"
        f"Plan {low} to {high} scenes for a {video['width']}x{video['height']} vertical "
        "video, one scene per script beat, in beat order.\n\n"
        f"There are {image_count} product images, indexed 0..{max(image_count - 1, 0)}. "
        "Every scene must name one via `image_index`; prefer a different image per "
        "scene. Scene durations must sum to the script's estimated duration.\n\n"
        "`kind` is one of: title, feature, spec, cta. Use exactly one title scene "
        "first and exactly one cta scene last.\n\n"
        "`headline` is 6 words or fewer and is burned onto the frame in uppercase. "
        "`subline` is 12 words or fewer. For a `spec` scene, `spec_pills` holds 2-3 "
        "{label, value} pairs copied verbatim from the scraped specs.\n\n"
        "# JSON KEYS\n"
        '{"scenes": [{"kind": str, "beat": str, "image_index": number, '
        '"duration_seconds": number, "headline": str, "subline": str, '
        '"spec_pills": [{"label": str, "value": str}]}], "total_duration_seconds": number}'
        f"{revision_directive(state.get('revision'))}"
    )
    return system, user
