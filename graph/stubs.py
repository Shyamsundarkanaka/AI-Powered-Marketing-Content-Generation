"""Documented fallback outputs — what each node returns when the LLM is unreachable.

These are fixed, uniform placeholder copy — deliberately identical across every
product — so a reviewer can never mistake stub content for a real generation.
The pipeline's *technical* scaffolding (image indices, scene durations from the
brand config) still uses the real scraped data, so the rest of the pipeline —
the video plan, the renderer, the timing of the silent voiceover — exercises
the same code paths it would with live model output, and the rendered video is
a genuine artifact rather than a mock. Only the visible text is a fixed dummy.

Every stub is tagged `source="stub"` by the caller and shown with a STUB badge in
the review UI, so placeholder copy is never mistaken for generated copy.
"""
from __future__ import annotations

from typing import Any

from brand.loader import load_brand

PLACEHOLDER_NOTE = "[Placeholder — set a real ANTHROPIC_API_KEY in .env to generate real content]"


def _spec_items(scraped: dict[str, Any], limit: int = 3) -> list[tuple[str, str]]:
    specs = scraped.get("specs") or {}
    return list(specs.items())[:limit]


# --- Campaign brief ----------------------------------------------------------

def stub_campaign_brief(state: dict[str, Any]) -> dict[str, Any]:
    return {
        "objective": f"{PLACEHOLDER_NOTE} Sample objective: drive qualified product-page visits from short-form social video.",
        "target_persona": "urban-commuter",
        "persona_rationale": f"{PLACEHOLDER_NOTE} Sample persona rationale.",
        "key_message": f"{PLACEHOLDER_NOTE} Sample key message goes here.",
        "proof_points": [
            {"claim": "Sample proof point one", "source": "placeholder"},
            {"claim": "Sample proof point two", "source": "placeholder"},
            {"claim": "Sample proof point three", "source": "placeholder"},
        ],
        "channels": ["Instagram Reels", "YouTube Shorts", "Product page"],
        "success_metric": "Click-through rate to the product page, measured over 14 days.",
    }


# --- Script ------------------------------------------------------------------

def stub_script(state: dict[str, Any]) -> dict[str, Any]:
    beats = [
        {"beat": "hook", "line": f"{PLACEHOLDER_NOTE} Sample hook line.", "on_screen": "Sample hook"},
        {"beat": "problem", "line": "Sample problem line.", "on_screen": "Sample problem"},
        {"beat": "product_reveal", "line": "Sample product reveal line.", "on_screen": "Sample product"},
        {"beat": "proof", "line": "Sample proof line.", "on_screen": "Sample proof"},
        {"beat": "cta", "line": "Sample call to action line.", "on_screen": "Learn more"},
    ]
    words = sum(len(beat["line"].split()) for beat in beats)
    wps = load_brand().content_rules["script"]["words_per_second"]
    return {
        "title": "Sample script title",
        "beats": beats,
        "estimated_duration_seconds": round(words / wps, 1),
    }


# --- Caption -----------------------------------------------------------------

def stub_caption(state: dict[str, Any]) -> dict[str, Any]:
    first_line = "Sample caption first line 🛹"
    caption = (
        f"{first_line}\n\n"
        f"{PLACEHOLDER_NOTE} This is sample caption body text, the same for every product "
        "until a real API key is configured.\n\n"
        "Sample call to action — full specs on the product page."
    )
    return {
        "caption": caption,
        "first_line": first_line,
        "cta": "Full specs on the product page",
        "char_count": len(caption),
    }


# --- Hashtags ----------------------------------------------------------------

def stub_hashtags(state: dict[str, Any]) -> dict[str, Any]:
    tags = [
        "#placeholder",
        "#samplehashtag",
        "#hoverboard",
        "#electricmobility",
        "#lastmile",
        "#commutelife",
        "#ridetowork",
        "#personaltransport",
        "#urbanmobility",
        "#indiaonwheels",
    ]
    return {
        "hashtags": tags[:10],
        "rationale": f"{PLACEHOLDER_NOTE} Sample rationale text.",
    }


# --- Video plan --------------------------------------------------------------

def stub_video_plan(state: dict[str, Any]) -> dict[str, Any]:
    scraped = state["scraped"]
    beats = state["script"]["beats"]
    image_count = max(len(scraped.get("image_urls") or []), 1)
    brand = load_brand()

    kinds = {
        "hook": "feature",
        "problem": "feature",
        "product_reveal": "title",
        "proof": "spec",
        "cta": "cta",
    }
    # Title first, CTA last — the renderer relies on that ordering for its
    # title/CTA card treatments, so the stub must honour it too.
    scenes: list[dict[str, Any]] = []
    total = float(state["script"].get("estimated_duration_seconds") or 28)
    body_beats = [b for b in beats if b["beat"] not in ("cta",)]
    title_seconds = brand.video["title_card_seconds"]
    cta_seconds = brand.video["cta_card_seconds"]
    per_body = max((total - title_seconds - cta_seconds) / max(len(body_beats) - 1, 1), 3.0)

    scenes.append(
        {
            "kind": "title",
            "beat": "title",
            "image_index": 0,
            "duration_seconds": title_seconds,
            "headline": "Sample Product",
            "subline": "Sample price",
            "spec_pills": [],
        }
    )

    index = 1
    for beat in body_beats:
        if beat["beat"] == "product_reveal":
            continue  # already covered by the title card
        kind = kinds.get(beat["beat"], "feature")
        pills = (
            [{"label": key, "value": value} for key, value in _spec_items(scraped, limit=3)]
            if kind == "spec"
            else []
        )
        scenes.append(
            {
                "kind": kind,
                "beat": beat["beat"],
                "image_index": index % image_count,
                "duration_seconds": round(per_body, 1),
                "headline": beat.get("on_screen") or "Sample",
                "subline": beat["line"][:70],
                "spec_pills": pills,
            }
        )
        index += 1

    scenes.append(
        {
            "kind": "cta",
            "beat": "cta",
            "image_index": index % image_count,
            "duration_seconds": cta_seconds,
            "headline": "Ride it home",
            "subline": "radboards.in",
            "spec_pills": [],
        }
    )
    return {
        "scenes": scenes,
        "total_duration_seconds": round(sum(s["duration_seconds"] for s in scenes), 1),
    }
