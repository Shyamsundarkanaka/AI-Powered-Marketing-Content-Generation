"""Generate a full brand/ folder — brand.yaml + the four prose companions — from
a live Shopify store URL, so the app can be repointed at any Shopify brand
without hand-authoring brand.yaml again.

Five focused prompts, each responsible for one section of brand.yaml, run
against the same scraped-catalog signal (`brand/site_signals.py`). Splitting by
section keeps each prompt small enough for the model to reason well about.

If any section can't be generated, the whole command fails and writes nothing.
A brand document is the input to every agent prompt and every rendered frame,
so a partially-invented one would silently mis-brand everything produced from
it — far worse than having no brand file at all.

Usage:
    python -m brand.generate https://your-store.myshopify.com

This overwrites the live brand/ folder the app reads from (config.settings.
BRAND_DIR), after moving whatever was there into brand_backups/<name>_<timestamp>/
so the swap is reversible. No other code changes are required — every agent
prompt and the video renderer already read brand.yaml generically, not by
hardcoded brand name.

To preview without touching the live brand, pass --out:
    python -m brand.generate https://your-store.myshopify.com --out brand_preview
"""
from __future__ import annotations

import argparse
import json
import logging
import shutil
from datetime import datetime
from pathlib import Path
from typing import Any

import yaml

from brand.loader import BrandDefinitionError, validate_brand_document
from brand.site_signals import SiteSignalError, collect_signals
from config.settings import BASE_DIR, BRAND_DIR
from graph.llm import LLMError, SchemaError, generate_json

logger = logging.getLogger(__name__)

# Rendering constants are a platform fact (Reels/Shorts/TikTok safe areas), not a
# brand fact — no prompt needed, every brand gets the same technically-correct
# defaults and can hand-tune them afterwards like Radboards' own brand.yaml does.
DEFAULT_VIDEO = {
    "aspect": "vertical",
    "width": 1080,
    "height": 1920,
    "fps": 30,
    "safe_area": {"top": 220, "bottom": 380, "left": 72, "right": 72},
    "ken_burns": {"zoom_start": 1.06, "zoom_end": 1.18, "max_pan_px": 90},
    "transition_seconds": 0.45,
    "title_card_seconds": 2.2,
    "cta_card_seconds": 3.0,
}


def _catalog_block(signals: dict[str, Any]) -> str:
    lines = [f"Store: {signals['root_url']}"]
    if signals.get("site_title"):
        lines.append(f"Site title: {signals['site_title']}")
    if signals.get("meta_description"):
        lines.append(f"Meta description: {signals['meta_description']}")
    if signals.get("about_snippet"):
        lines.append(f"About page excerpt: {signals['about_snippet']}")
    if signals.get("currency_code"):
        lines.append(f"Currency code: {signals['currency_code']}")
    lines.append(f"\nSample products ({len(signals['sample_products'])}):")
    for p in signals["sample_products"]:
        price = f"{p['price_min']}-{p['price_max']}" if p["price_min"] is not None else "n/a"
        lines.append(f"- {p['title']} | type: {p['product_type']} | tags: {p['tags']} | price: {price}")
        if p["description"]:
            lines.append(f"    {p['description']}")
    return "\n".join(lines)


JSON_CONTRACT = (
    "Reply with a single JSON object and nothing else. No prose before or after, "
    "no markdown fence. Use the exact keys described; do not add keys."
)


def _system(role: str) -> str:
    return f"{role}\n\n# OUTPUT\n{JSON_CONTRACT}"


# --- 1. Core identity ---------------------------------------------------------

IDENTITY_KEYS = ("name", "category", "market", "currency_symbol", "one_liner", "positioning")


def _identity_prompt(signals: dict[str, Any]) -> tuple[str, str]:
    system = _system(
        "You are a brand strategist. Given raw signals scraped from a Shopify "
        "store's homepage and product catalog, infer the brand's core identity."
    )
    user = (
        f"{_catalog_block(signals)}\n\n"
        "# TASK\nInfer this store's brand identity.\n\n"
        "# JSON KEYS\n"
        '{"name": str, "category": str (one line, what kind of products these are), '
        '"market": str (country/region this store most obviously targets), '
        '"currency_symbol": str (e.g. "$", "₹", "€" — infer from currency code or prices), '
        '"one_liner": str (<=8 words, brand tagline), '
        '"positioning": str (2-3 sentences: who this is for and what makes it different)}'
    )
    return system, user



# --- 2. Voice & language ------------------------------------------------------

VOICE_KEYS = ("voice", "language")


def _voice_prompt(signals: dict[str, Any], identity: dict[str, Any]) -> tuple[str, str]:
    system = _system(
        "You are a brand copywriter defining a voice and tone system for an AI "
        "content pipeline to follow exactly. Be specific and concrete — vague "
        "adjectives are useless as instructions to a model."
    )
    user = (
        f"# BRAND\n{json.dumps(identity, ensure_ascii=False)}\n\n"
        f"{_catalog_block(signals)}\n\n"
        "# TASK\nDefine the brand voice and language rules.\n\n"
        "# JSON KEYS\n"
        '{"voice": {"archetype": str, "personality": [str, 3-6 traits], '
        '"tone_by_context": {"campaign_brief": str, "script": str, "caption": str, "hashtags": str}, '
        '"principles": [str, 3-5 concrete writing rules], '
        '"we_say": [str, words/phrases on-brand], '
        '"we_never_say": [str, words/phrases and claim types to avoid — include generic hype '
        "words like revolutionary/game-changing plus anything unsafe for this specific "
        'product category (e.g. medical claims for a supplement brand)]}, '
        '"language": {"reading_level": str, "sentence_max_words": number, '
        '"emoji": {"caption": str, "script": str, "campaign_brief": str}, '
        '"numbers": str (one instruction on how to render prices/specs faithfully)}}'
    )
    return system, user



# --- 3. Audience & personas ---------------------------------------------------

AUDIENCE_KEYS = ("primary", "personas")


def _audience_prompt(signals: dict[str, Any], identity: dict[str, Any]) -> tuple[str, str]:
    system = _system(
        "You are a customer research strategist. Given a product catalog, define "
        "2 to 3 realistic buyer personas the marketing content should target."
    )
    user = (
        f"# BRAND\n{json.dumps(identity, ensure_ascii=False)}\n\n"
        f"{_catalog_block(signals)}\n\n"
        "# TASK\nDefine 2 to 3 buyer personas grounded in this actual catalog "
        "(price points, product types) — not generic stock personas.\n\n"
        "# JSON KEYS\n"
        '{"primary": str (id of the single most common persona), '
        '"personas": [{"id": str (kebab-case slug), "name": str (first name + age), '
        '"snapshot": str (2-3 sentences: who they are, life context), '
        '"wants": [str, 3], "fears": [str, 3], '
        '"hook_that_works": str (one sentence on what messaging lands for them)}]}'
    )
    return system, user



# --- 4. Content & compliance rules --------------------------------------------

RULES_KEYS = ("content_rules", "compliance")


def _rules_prompt(signals: dict[str, Any], identity: dict[str, Any]) -> tuple[str, str]:
    system = _system(
        "You are a brand compliance and content-ops lead. Define format rules for "
        "each content type and hard compliance boundaries appropriate to this "
        "product category — the boundaries must reflect real regulatory/ethical "
        "risk for this specific category (e.g. supplements need different "
        "guardrails than apparel)."
    )
    user = (
        f"# BRAND\n{json.dumps(identity, ensure_ascii=False)}\n\n"
        f"{_catalog_block(signals)}\n\n"
        "# TASK\nDefine content format rules and compliance rules.\n\n"
        "# JSON KEYS\n"
        '{"content_rules": {'
        '"campaign_brief": {"sections": [str], "proof_points_min": number, "note": str}, '
        '"script": {"duration_seconds": [number, number], "words_per_second": number, '
        '"structure": [str, 5 beats], "hook_max_words": number, "note": str}, '
        '"caption": {"max_chars": number, "first_line_max_chars": number, "cta_required": true, "note": str}, '
        '"hashtags": {"count": [number, number], "always_include": [str, one brand hashtag], '
        '"style": str, "banned": [str]}, '
        '"video_plan": {"scene_count": [number, number], "aspect": "vertical", "note": str}}, '
        '"compliance": {"must": [str, 2-4 rules], "must_not": [str, 3-5 category-specific rules], '
        '"disclosure": str (one sentence disclaimer to include when relevant)}}'
    )
    return system, user



# --- 5. Visual identity --------------------------------------------------------

VISUAL_KEYS = ("palette", "typography", "logo")


def _visual_prompt(signals: dict[str, Any], identity: dict[str, Any]) -> tuple[str, str]:
    theme_color = signals.get("theme_color") or "(none detected)"
    system = _system(
        "You are a brand designer choosing a video-safe color palette and "
        "typography system. Prefer the site's own theme color as the primary "
        "accent when one was detected — don't invent a clashing palette."
    )
    user = (
        f"# BRAND\n{json.dumps(identity, ensure_ascii=False)}\n\n"
        f"Detected site theme-color: {theme_color}\n\n"
        "# TASK\nDefine a palette and typography system for short-form vertical "
        "video overlays (text must stay readable over photography).\n\n"
        "# JSON KEYS\n"
        '{"palette": {"ink": "#hex (dark background/letterbox)", '
        '"surface": "#hex (cards/plates)", "primary": "#hex (CTA/key numbers — use '
        "detected theme-color if given)\", \"accent\": \"#hex (secondary highlight)\", "
        '"paper": "#hex (light text on dark)", "muted": "#hex (secondary text)"}, '
        '"typography": {"display": {"case": "upper or sentence", "tracking": number}, '
        '"body": {"case": "sentence", "tracking": 0}}, '
        '"logo": {"wordmark": str (brand name, how it should render in the video lockup)}}'
    )
    return system, user



# --- Orchestration --------------------------------------------------------------


def _require_keys(node: str, keys: tuple[str, ...]) -> Any:
    """A validator for `generate_json`: every key present and non-empty.

    Deliberately loose. Unlike the content pipeline, where a bad shape corrupts
    a downstream render, a brand document is written to disk for a human to
    read and edit before it is ever used — and `validate_brand_document()`
    checks the assembled result properly once all five sections are in.
    """

    def validate(payload: dict[str, Any]) -> dict[str, Any]:
        missing = [key for key in keys if not payload.get(key)]
        if missing:
            raise SchemaError(
                f"{node} is missing required keys: {', '.join(missing)}. "
                f"Include every key described, with a non-empty value."
            )
        return payload

    return validate


def _section(node: str, prompt: tuple[str, str], keys: tuple[str, ...]) -> dict[str, Any]:
    system, user = prompt
    return generate_json(
        node=node, system=system, user=user, validator=_require_keys(node, keys)
    ).payload


def generate_brand(store_url: str) -> dict[str, Any]:
    """Run the five section prompts against one store's scraped signals and
    assemble a brand.yaml-shaped dict.

    Raises `LLMError` if any section cannot be generated, and
    `BrandDefinitionError` if the five sections together don't add up to a
    usable brand document. A half-invented brand file is worse than none: every
    downstream agent prompt and the entire renderer are built from it, so a
    plausible-looking placebo would quietly mis-brand every asset produced
    afterwards.
    """
    signals = collect_signals(store_url)

    identity = _section("brand_identity", _identity_prompt(signals), IDENTITY_KEYS)
    voice = _section("brand_voice", _voice_prompt(signals, identity), VOICE_KEYS)
    audience = _section("brand_audience", _audience_prompt(signals, identity), AUDIENCE_KEYS)
    rules = _section("brand_rules", _rules_prompt(signals, identity), RULES_KEYS)
    visual = _section("brand_visual", _visual_prompt(signals, identity), VISUAL_KEYS)

    brand = {
        "name": identity["name"],
        "category": identity["category"],
        "market": identity["market"],
        "currency_symbol": identity["currency_symbol"],
        "website": signals["root_url"],
        "one_liner": identity["one_liner"],
        "positioning": identity["positioning"],
    }

    document = {
        "brand": brand,
        "voice": voice["voice"],
        "audience": audience,
        "language": voice["language"],
        "content_rules": rules["content_rules"],
        "compliance": rules["compliance"],
        "visual": {
            "palette": visual["palette"],
            "gradient_scrim": [visual["palette"]["ink"], visual["palette"]["ink"] + "00"],
            "typography": {
                "display": {
                    "family": "Arial",
                    "candidates": ["arialbd.ttf", "DejaVuSans-Bold.ttf"],
                    **visual["typography"]["display"],
                },
                "body": {
                    "family": "Arial",
                    "candidates": ["arial.ttf", "DejaVuSans.ttf"],
                    **visual["typography"]["body"],
                },
            },
            "video": DEFAULT_VIDEO,
            "logo": {
                "wordmark": visual["logo"]["wordmark"],
                "lockup_position": "top-left",
                "clear_space_px": 48,
            },
        },
    }

    # The five sections are individually plausible; this is the check that they
    # combine into something every downstream consumer can actually read.
    return validate_brand_document(document)


# --- Writing the brand/ folder --------------------------------------------------

_YAML_HEADER = """\
# {name} brand system — machine-readable source of truth.
# Generated by `python -m brand.generate` from {website}. Review before use.
#
# Two consumers read this file:
#   1. graph/prompts.py  — injects `voice`, `audience`, `language`, `compliance`
#                          and `content_rules` into every agent prompt.
#   2. media/movie.py    — reads `visual` for colours, fonts and layout safe areas.
"""


def write_brand_yaml(data: dict[str, Any], out_dir: Path) -> Path:
    path = out_dir / "brand.yaml"
    header = _YAML_HEADER.format(name=data["brand"]["name"], website=data["brand"]["website"])
    body = yaml.safe_dump(data, sort_keys=False, allow_unicode=True, width=100)
    path.write_text(header + "\n" + body, encoding="utf-8")
    return path


def _list_md(items: list[str]) -> str:
    return "\n".join(f"- {item}" for item in items)


def write_prose_docs(data: dict[str, Any], out_dir: Path) -> list[Path]:
    """Render the four human-readable companions straight from the same
    structured data written to brand.yaml, so they can't drift from it — no
    separate LLM call, just formatting.
    """
    brand, voice, audience, rules, compliance, visual = (
        data["brand"],
        data["voice"],
        data["audience"],
        data["content_rules"],
        data["compliance"],
        data["visual"],
    )
    paths = []

    guidelines = (
        f"# {brand['name']} — Brand Guidelines\n\n"
        f"**Positioning:** {brand['positioning']}\n\n"
        f"**One-liner:** {brand['one_liner']}\n\n"
        f"## Voice\n**Archetype:** {voice['archetype']}\n\n"
        f"**Personality:** {', '.join(voice['personality'])}\n\n"
        f"### Principles\n{_list_md(voice['principles'])}\n\n"
        f"### We say\n{_list_md(voice['we_say'])}\n\n"
        f"### We never say\n{_list_md(voice['we_never_say'])}\n\n"
        f"## Tone by context\n"
        + "\n".join(f"- **{k}:** {v}" for k, v in voice["tone_by_context"].items())
        + "\n"
    )
    p = out_dir / "BRAND_GUIDELINES.md"
    p.write_text(guidelines, encoding="utf-8")
    paths.append(p)

    personas_md = [f"# {brand['name']} — Personas\n\nPrimary: `{audience['primary']}`\n"]
    for persona in audience["personas"]:
        personas_md.append(
            f"\n## {persona['name']} (`{persona['id']}`)\n"
            f"{persona['snapshot']}\n\n"
            f"**Wants:** {', '.join(persona['wants'])}\n\n"
            f"**Fears:** {', '.join(persona['fears'])}\n\n"
            f"**Hook that works:** {persona['hook_that_works']}\n"
        )
    p = out_dir / "PERSONAS.md"
    p.write_text("".join(personas_md), encoding="utf-8")
    paths.append(p)

    visual_md = (
        f"# {brand['name']} — Visual Identity\n\n"
        "## Palette\n"
        + "\n".join(f"- **{k}:** `{v}`" for k, v in visual["palette"].items())
        + f"\n\n## Typography\nDisplay: {visual['typography']['display']['family']} "
        f"({visual['typography']['display']['case']})\n\n"
        f"Body: {visual['typography']['body']['family']} ({visual['typography']['body']['case']})\n\n"
        f"## Logo\nWordmark: **{visual['logo']['wordmark']}**, {visual['logo']['lockup_position']}\n\n"
        f"## Video\n{visual['video']['width']}x{visual['video']['height']} @ {visual['video']['fps']}fps, "
        f"{visual['video']['aspect']}\n"
    )
    p = out_dir / "VISUAL_IDENTITY.md"
    p.write_text(visual_md, encoding="utf-8")
    paths.append(p)

    compliance_md = (
        f"# {brand['name']} — Compliance\n\n"
        f"## Must\n{_list_md(compliance['must'])}\n\n"
        f"## Must not\n{_list_md(compliance['must_not'])}\n\n"
        f"## Disclosure\n{compliance['disclosure']}\n\n"
        f"## Content rules\n```\n{yaml.safe_dump(rules, sort_keys=False, allow_unicode=True)}```\n"
    )
    p = out_dir / "COMPLIANCE.md"
    p.write_text(compliance_md, encoding="utf-8")
    paths.append(p)

    return paths


BACKUP_ROOT = BASE_DIR / "brand_backups"

# The only files this script ever writes or backs up. brand/ also holds this
# script's own code (generate.py, loader.py, site_signals.py, __init__.py) —
# those must never be touched, so backup/replace is scoped to exactly this list
# rather than operating on the whole directory.
GENERATED_FILENAMES = (
    "brand.yaml",
    "BRAND_GUIDELINES.md",
    "PERSONAS.md",
    "VISUAL_IDENTITY.md",
    "COMPLIANCE.md",
)


def _backup_existing(out_dir: Path) -> Path | None:
    """Copy the current generated data files (not the whole folder — brand/ also
    holds this script's own code) into a timestamped folder under
    brand_backups/, then delete them from out_dir. Returns the backup path, or
    None if none of them existed yet.
    """
    existing = [out_dir / name for name in GENERATED_FILENAMES if (out_dir / name).exists()]
    if not existing:
        return None
    BACKUP_ROOT.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d_%H%M%S")
    dest = BACKUP_ROOT / f"{out_dir.name}_{stamp}"
    dest.mkdir(parents=True)
    for path in existing:
        shutil.move(str(path), str(dest / path.name))
    return dest


def main() -> None:
    logging.basicConfig(level=logging.INFO)
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("store_url", help="Any product/collection/home URL on the target Shopify store")
    parser.add_argument(
        "--out",
        default=None,
        help="Output directory. Defaults to the live brand/ folder the app reads "
        "(config.settings.BRAND_DIR) — pass a different path to preview without "
        "touching the live brand.",
    )
    parser.add_argument(
        "--no-backup",
        action="store_true",
        help="Skip backing up the existing folder before overwriting it. Only "
        "relevant when writing to the live brand/ folder.",
    )
    args = parser.parse_args()

    out_dir = Path(args.out) if args.out else BRAND_DIR
    replacing_live = out_dir.resolve() == BRAND_DIR.resolve()

    # Generate first, write second: nothing touches the live brand/ folder
    # (and no backup is taken) unless there is a complete, valid document to
    # replace it with.
    try:
        data = generate_brand(args.store_url)
    except (SiteSignalError, LLMError, BrandDefinitionError) as exc:
        raise SystemExit(f"Brand generation failed, nothing was written: {exc}") from None

    backup_path = None if args.no_backup else _backup_existing(out_dir)
    out_dir.mkdir(parents=True, exist_ok=True)

    yaml_path = write_brand_yaml(data, out_dir)
    doc_paths = write_prose_docs(data, out_dir)

    print(f"\nGenerated brand for '{data['brand']['name']}' -> {out_dir}/")
    for p in [yaml_path, *doc_paths]:
        print(f"  - {p}")
    if backup_path:
        print(f"\nPrevious brand backed up to: {backup_path}")
    if replacing_live:
        print("\nThe live brand/ folder now reflects this brand — no other steps needed.")
    else:
        print(
            f"\nThis was written to a preview folder, not the live brand/. Re-run without "
            f"--out (or with --out {BRAND_DIR}) to make it live."
        )


if __name__ == "__main__":
    main()
