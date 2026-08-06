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
    """Parse brand.yaml once per process."""
    data = yaml.safe_load(BRAND_YAML_PATH.read_text(encoding="utf-8"))
    logger.info("Loaded brand definition for %s", data["brand"]["name"])
    return Brand(data)
