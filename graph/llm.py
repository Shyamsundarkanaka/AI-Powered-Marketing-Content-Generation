"""The single place the system talks to an LLM, and the single place it gives up.

Every agent node calls `generate_json()`. It attempts a real Claude call and, if
anything at all goes wrong — bad API key, network down, rate limit, malformed or
schema-violating response — it falls back to that node's documented stub output
and reports `source="stub"`.

This is what makes the dummy-key default work: the pipeline runs end to end and
produces every artifact, and the provenance is recorded honestly so no one
mistakes canned copy for generated copy.
"""
from __future__ import annotations

import functools
import json
import logging
import re
from typing import Any, Callable, Optional

from config.settings import (
    ANTHROPIC_API_KEY,
    ANTHROPIC_MODEL,
    LLM_MAX_RETRIES,
    LLM_MAX_TOKENS,
    LLM_TIMEOUT_SECONDS,
)

logger = logging.getLogger(__name__)

SOURCE_LLM = "llm"
SOURCE_STUB = "stub"

_PLACEHOLDER_MARKERS = ("dummy", "placeholder", "changeme", "your-key", "xxx")


def looks_like_placeholder_key(key: str) -> bool:
    """Whether the configured key is obviously not a real one.

    Only used to make the log line explain *why* a call failed. The call is
    still attempted either way — the key might be real and simply revoked, and
    guessing is worse than asking the API.
    """
    lowered = (key or "").lower()
    return not lowered or any(marker in lowered for marker in _PLACEHOLDER_MARKERS)


@functools.lru_cache(maxsize=1)
def get_chat_model():
    """Build the Claude client once per process.

    Imported lazily so that anything importing this module for its constants
    (the Streamlit app never does, but the tests might) doesn't pay the
    langchain import cost.
    """
    from langchain_anthropic import ChatAnthropic

    return ChatAnthropic(
        model=ANTHROPIC_MODEL,
        api_key=ANTHROPIC_API_KEY,
        max_tokens=LLM_MAX_TOKENS,
        timeout=LLM_TIMEOUT_SECONDS,
        max_retries=LLM_MAX_RETRIES,
    )


class MalformedResponse(ValueError):
    """The model replied, but not with JSON matching the requested shape."""


def _extract_json(text: str) -> dict[str, Any]:
    """Pull a JSON object out of a model response.

    Handles the three shapes that actually show up: bare JSON, JSON inside a
    ```json fence, and JSON with a sentence of preamble in front of it.
    """
    candidate = text.strip()

    fenced = re.search(r"```(?:json)?\s*(.+?)\s*```", candidate, re.DOTALL)
    if fenced:
        candidate = fenced.group(1).strip()

    if not candidate.startswith("{"):
        start = candidate.find("{")
        end = candidate.rfind("}")
        if start == -1 or end <= start:
            raise MalformedResponse("no JSON object found in response")
        candidate = candidate[start : end + 1]

    try:
        parsed = json.loads(candidate)
    except json.JSONDecodeError as exc:
        raise MalformedResponse(f"invalid JSON: {exc}") from exc

    if not isinstance(parsed, dict):
        raise MalformedResponse(f"expected a JSON object, got {type(parsed).__name__}")
    return parsed


def _check_required(payload: dict[str, Any], required_keys: tuple[str, ...]) -> None:
    missing = [key for key in required_keys if key not in payload]
    if missing:
        raise MalformedResponse(f"missing required keys: {', '.join(missing)}")


def generate_json(
    *,
    node: str,
    system: str,
    user: str,
    required_keys: tuple[str, ...],
    stub_factory: Callable[[], dict[str, Any]],
) -> tuple[dict[str, Any], str, Optional[str]]:
    """Ask Claude for a JSON object; fall back to the node's stub on any failure.

    Returns `(payload, source, error)` where source is `"llm"` or `"stub"` and
    error is the reason for the fallback (None on success). Callers record both
    so the reviewer can see exactly which artifacts are canned.
    """
    from langchain_core.messages import HumanMessage, SystemMessage

    try:
        response = get_chat_model().invoke(
            [SystemMessage(content=system), HumanMessage(content=user)]
        )
        text = response.content
        if isinstance(text, list):
            # Content blocks (thinking + text): keep the text ones.
            text = "".join(
                block.get("text", "")
                for block in text
                if isinstance(block, dict) and block.get("type") == "text"
            )
        payload = _extract_json(text)
        _check_required(payload, required_keys)
    except Exception as exc:  # noqa: BLE001 — any failure must degrade to a stub
        reason = f"{type(exc).__name__}: {exc}"
        if looks_like_placeholder_key(ANTHROPIC_API_KEY):
            reason += " (ANTHROPIC_API_KEY looks like a placeholder — set a real key in .env)"
        logger.warning("Node %s: LLM unavailable, using stub output. %s", node, reason)
        payload = stub_factory()
        return payload, SOURCE_STUB, reason

    logger.info("Node %s: generated via %s", node, ANTHROPIC_MODEL)
    return payload, SOURCE_LLM, None
