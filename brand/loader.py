"""Loads and exposes `brand.yaml` to the two things that consume it.

The agents (via `graph/prompts.py`) need voice, audience, language, content and
compliance rules rendered as a prompt block. The renderer (`media/movie.py`)
needs colours, fonts and layout numbers as typed values. Both come from the same
parse, cached for the process lifetime — the file does not change at runtime.
"""
from __future__ import annotations

import functools
import logging
from pathlib import Path
from typing import Any

import yaml

from config.settings import BRAND_DIR

logger = logging.getLogger(__name__)

BRAND_YAML_PATH = BRAND_DIR / "brand.yaml"


class BrandDefinitionError(ValueError):
    """`brand.yaml` is missing something the code will later require."""


# Every path the rest of the codebase reads out of brand.yaml, as
# dotted keys. `[]` marks a list that must be non-empty.
#
# This exists because the failure mode without it is terrible: a brand file
# missing `content_rules.script.words_per_second` parses fine, loads fine, and
# then dies with a bare KeyError inside the voiceover node twenty seconds into
# a paid pipeline run. Checking once at load turns that into one clear message.
REQUIRED_PATHS: tuple[str, ...] = (
    "brand.name", "brand.currency_symbol", "brand.website", "brand.one_liner",
    "brand.category", "brand.market", "brand.positioning",
    "voice", "language", "language.emoji.caption",
    "audience.primary", "audience.personas[]",
    "content_rules.campaign_brief.proof_points_min",
    "content_rules.script.duration_seconds[]", "content_rules.script.words_per_second",
    "content_rules.script.structure[]", "content_rules.script.hook_max_words",
    "content_rules.caption.max_chars", "content_rules.caption.first_line_max_chars",
    "content_rules.hashtags.count[]", "content_rules.hashtags.always_include[]",
    "content_rules.video_plan.scene_count[]",
    "compliance.must[]", "compliance.must_not[]", "compliance.disclosure",
    "visual.palette.ink", "visual.palette.surface", "visual.palette.primary",
    "visual.palette.accent", "visual.palette.paper", "visual.palette.muted",
    "visual.gradient_scrim[]",
    "visual.typography.display.candidates[]", "visual.typography.display.case",
    "visual.typography.body.candidates[]",
    "visual.video.width", "visual.video.height", "visual.video.fps",
    "visual.video.safe_area.top", "visual.video.safe_area.bottom",
    "visual.video.safe_area.left", "visual.video.safe_area.right",
    "visual.video.ken_burns.zoom_start", "visual.video.ken_burns.zoom_end",
    "visual.video.ken_burns.max_pan_px",
    "visual.video.transition_seconds", "visual.video.title_card_seconds",
    "visual.video.cta_card_seconds",
    "visual.logo.wordmark",
)

PERSONA_KEYS = ("id", "name", "wants", "fears")


def _resolve_path(data: dict[str, Any], dotted: str) -> Any:
    node: Any = data
    for part in dotted.split("."):
        if not isinstance(node, dict) or part not in node:
            raise KeyError(dotted)
        node = node[part]
    return node


def validate_brand_document(data: Any) -> dict[str, Any]:
    """Check a parsed brand document against everything the code reads.

    Returns the document so it can be used inline. Raises
    `BrandDefinitionError` listing *all* problems at once — fixing a generated
    brand file one missing key per run would be miserable.
    """
    if not isinstance(data, dict):
        raise BrandDefinitionError(f"brand.yaml must be a mapping, got {type(data).__name__}")

    problems: list[str] = []
    for path in REQUIRED_PATHS:
        wants_list = path.endswith("[]")
        dotted = path[:-2] if wants_list else path
        try:
            value = _resolve_path(data, dotted)
        except KeyError:
            problems.append(f"missing: {dotted}")
            continue
        if wants_list and not (isinstance(value, (list, tuple)) and value):
            problems.append(f"{dotted} must be a non-empty list")
        elif not wants_list and value in (None, ""):
            problems.append(f"{dotted} must not be empty")

    personas = (data.get("audience") or {}).get("personas")
    if isinstance(personas, list):
        for index, persona in enumerate(personas):
            if not isinstance(persona, dict):
                problems.append(f"audience.personas[{index}] must be a mapping")
                continue
            missing = [key for key in PERSONA_KEYS if not persona.get(key)]
            if missing:
                problems.append(f"audience.personas[{index}] missing: {', '.join(missing)}")

    for pair_path in ("content_rules.script.duration_seconds", "content_rules.hashtags.count",
                      "content_rules.video_plan.scene_count"):
        try:
            pair = _resolve_path(data, pair_path)
        except KeyError:
            continue
        if not (isinstance(pair, (list, tuple)) and len(pair) == 2 and pair[0] <= pair[1]):
            problems.append(f"{pair_path} must be a [low, high] pair with low <= high")

    if problems:
        raise BrandDefinitionError(
            f"{BRAND_YAML_PATH} is not usable:\n  - " + "\n  - ".join(problems)
        )
    return data


class Brand:
    """Typed-ish accessor over the parsed brand.yaml.

    Deliberately thin: the YAML is the schema, and wrapping every nested key in a
    dataclass would mean editing Python every time the brand gains a rule. What
    this class adds is the *derived* views — `prompt_block()` for the agents and
    the colour/font helpers for the renderer.
    """

    def __init__(self, data: dict[str, Any]) -> None:
        self._data = data

    # --- raw sections -------------------------------------------------------

    @property
    def raw(self) -> dict[str, Any]:
        return self._data

    @property
    def name(self) -> str:
        return self._data["brand"]["name"]

    @property
    def currency_symbol(self) -> str:
        return self._data["brand"].get("currency_symbol", "")

    @property
    def visual(self) -> dict[str, Any]:
        return self._data["visual"]

    @property
    def video(self) -> dict[str, Any]:
        return self._data["visual"]["video"]

    @property
    def content_rules(self) -> dict[str, Any]:
        return self._data["content_rules"]

    @property
    def personas(self) -> list[dict[str, Any]]:
        return self._data["audience"]["personas"]

    def persona(self, persona_id: str) -> dict[str, Any] | None:
        return next((p for p in self.personas if p["id"] == persona_id), None)

    # --- renderer helpers ---------------------------------------------------

    def color(self, token: str) -> tuple[int, int, int]:
        """Palette token -> RGB tuple. Raises on an unknown token, by design."""
        return hex_to_rgb(self.visual["palette"][token])

    def font_candidates(self, role: str) -> list[str]:
        """Ordered font filenames for `display` or `body`."""
        return list(self.visual["typography"][role]["candidates"])

    def tracking(self, role: str) -> int:
        return int(self.visual["typography"][role].get("tracking", 0))

    # --- agent prompt helper ------------------------------------------------

    def prompt_block(self) -> str:
        """The brand rules, rendered for injection into every agent prompt.

        Only the sections an agent can act on are included — the `visual` block is
        the renderer's business and would be pure token cost in a copy prompt.
        """
        sections = {
            "BRAND": self._data["brand"],
            "VOICE": self._data["voice"],
            "AUDIENCE": self._data["audience"],
            "LANGUAGE": self._data["language"],
            "CONTENT RULES": self._data["content_rules"],
            "COMPLIANCE": self._data["compliance"],
        }
        parts = []
        for heading, body in sections.items():
            rendered = yaml.safe_dump(body, sort_keys=False, allow_unicode=True).strip()
            parts.append(f"## {heading}\n{rendered}")
        return "\n\n".join(parts)


def hex_to_rgb(value: str) -> tuple[int, int, int]:
    """`#RRGGBB` (or `#RRGGBBAA`, alpha dropped) -> (r, g, b)."""
    raw = value.lstrip("#")
    return (int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16))


def hex_to_rgba(value: str, default_alpha: int = 255) -> tuple[int, int, int, int]:
    """`#RRGGBB` or `#RRGGBBAA` -> (r, g, b, a). Used for the gradient scrim."""
    raw = value.lstrip("#")
    r, g, b = int(raw[0:2], 16), int(raw[2:4], 16), int(raw[4:6], 16)
    a = int(raw[6:8], 16) if len(raw) >= 8 else default_alpha
    return (r, g, b, a)


@functools.lru_cache(maxsize=1)
def load_brand() -> Brand:
    """Parse and validate brand.yaml once per process."""
    try:
        raw = BRAND_YAML_PATH.read_text(encoding="utf-8")
    except OSError as exc:
        raise BrandDefinitionError(f"Could not read {BRAND_YAML_PATH}: {exc}") from exc
    try:
        data = yaml.safe_load(raw)
    except yaml.YAMLError as exc:
        raise BrandDefinitionError(f"{BRAND_YAML_PATH} is not valid YAML: {exc}") from exc

    validate_brand_document(data)
    logger.info("Loaded brand definition for %s", data["brand"]["name"])
    return Brand(data)


def reload_brand() -> Brand:
    """Drop the cache and re-read brand.yaml. For tests and `brand.generate`."""
    load_brand.cache_clear()
    return load_brand()
