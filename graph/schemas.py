"""Validation and normalization for every agent's JSON response.

Each validator takes the parsed payload and returns a *normalized* copy, or
raises `SchemaError` with a message written to be handed straight back to the
model as a correction.

The split between the two is the whole design:

* **Normalize** anything the code can fix correctly and unambiguously — a
  hashtag missing its `#`, an image index past the end of the array, a scene
  duration of zero, a `char_count` the model miscounted. Round-tripping to the
  model for these would be slow and would not make the result any better.
* **Raise** anything that needs judgement — a caption over the character limit,
  a script that is 12 seconds long when the brand calls for 25-32, a persona id
  that does not exist. Only the model can fix those, and `graph/llm.py` feeds
  the message back and asks it to.

Every limit comes from `brand.yaml`, so tightening a brand rule tightens
validation with no code change.
"""
from __future__ import annotations

import re
from typing import Any, Iterable, Optional

from brand.loader import load_brand
from graph.llm import SchemaError

SCENE_KINDS = ("title", "feature", "spec", "cta")
MAX_SPEC_PILLS = 3
DEFAULT_SCENE_SECONDS = 4.5

# How far outside the brand's duration window a script may land before the
# model is asked to rewrite it. The window is a target, not a hard contract —
# rejecting a 24.6s script against a 25s floor would burn a call for nothing.
DURATION_UNDER_TOLERANCE = 0.85
DURATION_OVER_TOLERANCE = 1.20


# --- primitives --------------------------------------------------------------

def _require_mapping(payload: Any, what: str) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise SchemaError(f"{what} must be a JSON object, not {type(payload).__name__}")
    return payload


def _text(
    payload: dict[str, Any],
    key: str,
    *,
    required: bool = True,
    max_chars: Optional[int] = None,
    default: str = "",
) -> str:
    """A non-empty trimmed string, with whitespace collapsed."""
    value = payload.get(key)
    if value is None or (isinstance(value, str) and not value.strip()):
        if required:
            raise SchemaError(f'"{key}" is required and must be a non-empty string')
        return default
    if isinstance(value, (list, dict)):
        raise SchemaError(f'"{key}" must be a string, not {type(value).__name__}')
    text = str(value).strip()
    if max_chars is not None and len(text) > max_chars:
        raise SchemaError(
            f'"{key}" is {len(text)} characters; it must be {max_chars} or fewer. '
            f"Rewrite it shorter rather than truncating mid-word."
        )
    return text


def _number(
    payload: dict[str, Any],
    key: str,
    *,
    default: Optional[float] = None,
    minimum: Optional[float] = None,
) -> Optional[float]:
    """A float, tolerating the numeric strings models often emit ("28.5s")."""
    value = payload.get(key)
    if value is None or value == "":
        return default
    if isinstance(value, bool):
        raise SchemaError(f'"{key}" must be a number')
    if isinstance(value, (int, float)):
        number = float(value)
    else:
        match = re.search(r"-?\d+(?:\.\d+)?", str(value))
        if not match:
            raise SchemaError(f'"{key}" must be a number, got {value!r}')
        number = float(match.group())
    if minimum is not None and number < minimum:
        return default if default is not None else minimum
    return number


def _sequence(payload: dict[str, Any], key: str) -> list[Any]:
    """A list, tolerating a single bare item where a list was asked for."""
    value = payload.get(key)
    if value is None:
        raise SchemaError(f'"{key}" is required and must be an array')
    if isinstance(value, (str, dict)):
        return [value]
    if not isinstance(value, (list, tuple)):
        raise SchemaError(f'"{key}" must be an array, not {type(value).__name__}')
    return list(value)


def _string_list(payload: dict[str, Any], key: str, *, min_items: int = 1) -> list[str]:
    items = [str(item).strip() for item in _sequence(payload, key) if str(item).strip()]
    if len(items) < min_items:
        raise SchemaError(f'"{key}" must contain at least {min_items} entries, got {len(items)}')
    return items


def _word_count(text: str) -> int:
    return len(text.split())


# --- campaign brief ----------------------------------------------------------

def campaign_brief(payload: Any) -> dict[str, Any]:
    payload = _require_mapping(payload, "the campaign brief")
    brand = load_brand()
    rules = brand.content_rules["campaign_brief"]
    persona_ids = [persona["id"] for persona in brand.personas]

    persona = _text(payload, "target_persona")
    if persona not in persona_ids:
        raise SchemaError(
            f'"target_persona" must be exactly one of these persona ids: '
            f'{", ".join(persona_ids)}. You gave "{persona}".'
        )

    minimum = int(rules.get("proof_points_min", 3))
    proof_points: list[dict[str, str]] = []
    for raw in _sequence(payload, "proof_points"):
        # A bare string is a usable proof point with an unnamed source; keep it
        # rather than failing the whole brief over a formatting slip.
        if isinstance(raw, str) and raw.strip():
            proof_points.append({"claim": raw.strip(), "source": "unattributed"})
        elif isinstance(raw, dict):
            claim = str(raw.get("claim") or "").strip()
            if claim:
                proof_points.append(
                    {"claim": claim, "source": str(raw.get("source") or "unattributed").strip()}
                )
    if len(proof_points) < minimum:
        raise SchemaError(
            f'"proof_points" must contain at least {minimum} entries, each an object with '
            f'"claim" and "source". You gave {len(proof_points)} usable ones.'
        )

    return {
        "objective": _text(payload, "objective"),
        "target_persona": persona,
        "persona_rationale": _text(payload, "persona_rationale", required=False),
        "key_message": _text(payload, "key_message"),
        "proof_points": proof_points,
        "channels": _string_list(payload, "channels"),
        "success_metric": _text(payload, "success_metric"),
    }


# --- script ------------------------------------------------------------------

def script(payload: Any) -> dict[str, Any]:
    payload = _require_mapping(payload, "the script")
    rules = load_brand().content_rules["script"]
    structure: list[str] = list(rules["structure"])
    words_per_second = float(rules["words_per_second"])
    low, high = (float(bound) for bound in rules["duration_seconds"])

    beats: list[dict[str, str]] = []
    for raw in _sequence(payload, "beats"):
        if not isinstance(raw, dict):
            raise SchemaError('every entry in "beats" must be an object with "beat" and "line"')
        name = str(raw.get("beat") or "").strip().lower().replace(" ", "_")
        line = str(raw.get("line") or "").strip()
        if not line:
            raise SchemaError(f'the "{name or "unnamed"}" beat has an empty "line"')
        beats.append({"beat": name, "line": line, "on_screen": str(raw.get("on_screen") or "").strip()})

    if [beat["beat"] for beat in beats] != structure:
        raise SchemaError(
            f'"beats" must contain exactly {len(structure)} entries whose "beat" values are, '
            f'in this order: {", ".join(structure)}. You gave: '
            f'{", ".join(beat["beat"] for beat in beats) or "(none)"}.'
        )

    # The model's own duration estimate is a guess it is not good at. The word
    # count is a fact, so the spoken length is recomputed here — and it is what
    # the voiceover and the video timing are built from, so a wrong estimate
    # would desynchronise the whole render.
    spoken_words = sum(_word_count(beat["line"]) for beat in beats)
    duration = spoken_words / words_per_second
    if duration < low * DURATION_UNDER_TOLERANCE or duration > high * DURATION_OVER_TOLERANCE:
        raise SchemaError(
            f"the script is {spoken_words} words, about {duration:.0f} seconds when spoken at "
            f"{words_per_second} words per second. It must land between {low:.0f} and "
            f"{high:.0f} seconds — rewrite it "
            f"{'longer' if duration < low else 'shorter'} and keep all "
            f"{len(structure)} beats."
        )

    hook_max = int(rules.get("hook_max_words", 12))
    hook = next((beat for beat in beats if beat["beat"] == structure[0]), None)
    if hook and _word_count(hook["line"]) > hook_max:
        raise SchemaError(
            f'the "{structure[0]}" beat is {_word_count(hook["line"])} words; it must be '
            f"{hook_max} or fewer so it lands before the viewer scrolls."
        )

    return {
        "title": _text(payload, "title"),
        "beats": beats,
        "estimated_duration_seconds": round(duration, 1),
        "word_count": spoken_words,
    }


# --- caption -----------------------------------------------------------------

def caption(payload: Any) -> dict[str, Any]:
    payload = _require_mapping(payload, "the caption")
    rules = load_brand().content_rules["caption"]
    max_chars = int(rules["max_chars"])
    first_line_max = int(rules["first_line_max_chars"])

    body = _text(payload, "caption", max_chars=max_chars)
    if "#" in body:
        raise SchemaError(
            'the caption must not contain hashtags — they are generated separately and '
            'appended by the publishing step. Remove every "#" tag from "caption".'
        )

    # Whatever the model reported, the first line of the caption is what the
    # platform actually truncates to, so that is what gets validated.
    actual_first_line = body.split("\n", 1)[0].strip()
    if len(actual_first_line) > first_line_max:
        raise SchemaError(
            f"the caption's first line is {len(actual_first_line)} characters; it must be "
            f"{first_line_max} or fewer, because that is all a viewer sees before the "
            f'"more" truncation. Shorten the opening line.'
        )

    cta = _text(payload, "cta", required=bool(rules.get("cta_required")))

    return {
        "caption": body,
        "first_line": actual_first_line,
        "cta": cta,
        "char_count": len(body),
    }


# --- hashtags ----------------------------------------------------------------

_TAG_ALLOWED = re.compile(r"[^a-z0-9_]")


def _normalize_tag(raw: Any) -> str:
    """`"#Ride To Work!"` -> `"#ridetowork"`. Empty string if nothing survives."""
    text = str(raw or "").strip().lstrip("#").lower()
    text = _TAG_ALLOWED.sub("", text.replace(" ", "").replace("-", ""))
    return f"#{text}" if text else ""


def hashtags(payload: Any) -> dict[str, Any]:
    payload = _require_mapping(payload, "the hashtag set")
    rules = load_brand().content_rules["hashtags"]
    low, high = (int(bound) for bound in rules["count"])
    banned = {_normalize_tag(tag) for tag in rules.get("banned", [])}
    always = [_normalize_tag(tag) for tag in rules.get("always_include", [])]

    tags: list[str] = []
    for raw in _sequence(payload, "hashtags"):
        tag = _normalize_tag(raw)
        if tag and tag not in banned and tag not in tags:
            tags.append(tag)

    # Required brand tags go first and are never subject to the count check —
    # they are brand policy, not the model's choice.
    for required in reversed(always):
        if required and required not in tags:
            tags.insert(0, required)

    if len(tags) < low:
        raise SchemaError(
            f'"hashtags" must contain {low} to {high} usable tags. After removing duplicates '
            f"and banned tags ({', '.join(sorted(banned)) or 'none'}), only {len(tags)} remain. "
            f"Provide more distinct, relevant tags."
        )

    return {
        "hashtags": tags[:high],
        "rationale": _text(payload, "rationale", required=False),
    }


# --- video plan --------------------------------------------------------------

def _spec_pills(raw: Any) -> list[dict[str, str]]:
    pills: list[dict[str, str]] = []
    if not isinstance(raw, (list, tuple)):
        return pills
    for item in raw:
        if not isinstance(item, dict):
            continue
        label = str(item.get("label") or "").strip()
        value = str(item.get("value") or "").strip()
        if label and value:
            pills.append({"label": label, "value": value})
    return pills[:MAX_SPEC_PILLS]


def video_plan(payload: Any, *, image_count: int, beats: Iterable[str] = ()) -> dict[str, Any]:
    """Validate a scene plan.

    `image_count` is how many product photos actually exist: an index past the
    end is wrapped rather than rejected, because which photo a scene uses is a
    detail no reviewer would fail a version over, and the renderer needs a
    valid index either way.
    """
    payload = _require_mapping(payload, "the video plan")
    brand = load_brand()
    rules = brand.content_rules["video_plan"]
    low, high = (int(bound) for bound in rules["scene_count"])
    beat_names = list(beats)

    raw_scenes = [scene for scene in _sequence(payload, "scenes") if isinstance(scene, dict)]
    if not low <= len(raw_scenes) <= high:
        raise SchemaError(
            f'"scenes" must contain {low} to {high} scene objects, one per script beat. '
            f"You gave {len(raw_scenes)}."
        )

    first_kind = str(raw_scenes[0].get("kind") or "").strip().lower()
    last_kind = str(raw_scenes[-1].get("kind") or "").strip().lower()
    if first_kind != "title" or last_kind != "cta":
        raise SchemaError(
            'the first scene must have "kind": "title" and the last must have "kind": "cta" — '
            f'the renderer gives those two distinct card treatments. Yours start with '
            f'"{first_kind or "missing"}" and end with "{last_kind or "missing"}".'
        )

    scenes: list[dict[str, Any]] = []
    for position, raw in enumerate(raw_scenes):
        kind = str(raw.get("kind") or "").strip().lower()
        if kind not in SCENE_KINDS:
            kind = "feature"

        duration = _number(raw, "duration_seconds", default=DEFAULT_SCENE_SECONDS, minimum=0.5)
        if kind == "title":
            duration = duration or float(brand.video["title_card_seconds"])
        elif kind == "cta":
            duration = duration or float(brand.video["cta_card_seconds"])

        index = int(_number(raw, "image_index", default=position) or 0)
        scenes.append(
            {
                "kind": kind,
                "beat": str(raw.get("beat") or (beat_names[position] if position < len(beat_names) else "")).strip(),
                "image_index": index % image_count if image_count > 0 else 0,
                "duration_seconds": round(float(duration), 2),
                "headline": str(raw.get("headline") or "").strip(),
                "subline": str(raw.get("subline") or "").strip(),
                "spec_pills": _spec_pills(raw.get("spec_pills")),
            }
        )

    return {
        "scenes": scenes,
        "total_duration_seconds": round(sum(scene["duration_seconds"] for scene in scenes), 2),
    }
