"""The node functions that make up the pipeline graph.

Each node is a plain `PipelineState -> dict` function: it reads what it needs
from state and returns only the keys it writes, which LangGraph merges. Nothing
here constructs the graph — that is `pipeline.py`'s job — so nodes stay
individually callable and testable.

Every agent node follows the same contract via `_run_agent()`: build a prompt,
ask the model, validate the response against the node's schema, and record the
provenance under `sources[node]`.

There is no fallback content. If a node's agent cannot produce a valid
response, `graph/llm.py` raises and the run fails — the reviewer sees a failed
job with the real error rather than placeholder copy dressed up as output.
"""
from __future__ import annotations

import functools
import json
import logging
import shutil
from pathlib import Path
from typing import Any, Callable, Optional

from brand.loader import load_brand
from database.repository import (
    add_log,
    add_output,
    create_version,
    get_product,
    get_scraped_data,
    list_versions_for_product,
    next_version_number,
    update_product_status,
)
from graph import prompts, schemas
from graph.llm import LLMResult, active_config, generate_json
from graph.state import PipelineState
from media import movie, voice

logger = logging.getLogger(__name__)

META_FILENAME = "_meta.json"
SOURCE_LLM = "llm"
SOURCE_CARRIED = "carried_forward"

# The five LLM agents that reviewer feedback can be scoped to. Order doesn't
# matter here — it's a lookup set, not the pipeline's execution order.
NODE_KEYS = ("campaign_brief", "script", "caption", "hashtags", "video_plan")

# If a node is in scope, everything that embeds its output in its own prompt
# must be in scope too, or the new version would pair a regenerated node with
# stale content that was written against the *old* version of it. caption,
# hashtags and video_plan have no downstream consumers among these five, so
# they cascade to nothing.
_SCOPE_CASCADE: dict[str, tuple[str, ...]] = {
    "campaign_brief": ("script", "caption", "hashtags", "video_plan"),
    "script": ("caption", "hashtags", "video_plan"),
}


def _expand_scope(selected: set[str]) -> Optional[set[str]]:
    """Turn the reviewer's raw node selection into the full set that must run.

    Returns `None` for "regenerate everything", which is the canonical form:
    an empty selection, all five selected, and a selection that *cascades* to
    all five (picking `campaign_brief` does) all mean the same thing, and
    collapsing them here keeps one representation of it in state and in logs.
    """
    every_node = set(NODE_KEYS)
    if not selected or selected >= every_node:
        return None

    expanded = set(selected)
    for node, forces in _SCOPE_CASCADE.items():
        if node in expanded:
            expanded.update(forces)
    return None if expanded >= every_node else expanded


# --- shared helpers ----------------------------------------------------------

def _log(state: PipelineState, message: str, level: str = "INFO") -> None:
    add_log(message, product_id=state.get("product_id"), job_id=state.get("job_id"), level=level)


def _carried_forward_payload(state: PipelineState, node: str) -> Optional[dict[str, Any]]:
    """The previous version's output for `node`, if feedback scoped this run
    away from it. Returns None when there's nothing to carry (no revision in
    play, node is in scope, or the previous version never produced it) —
    callers fall through to a normal LLM call in every one of those cases.
    """
    revision = state.get("revision")
    if not revision:
        return None
    scope = revision.get("scope")
    if scope is None or node in scope:
        return None
    carried = (revision.get("carry_forward") or {}).get(node)
    if not isinstance(carried, dict) or not carried:
        return None
    payload = dict(carried)
    payload["_source"] = SOURCE_CARRIED
    return payload


def _run_agent(
    state: PipelineState,
    *,
    node: str,
    prompt_builder: Callable[[dict[str, Any]], tuple[str, str]],
    validator: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Run one generation agent and normalise the result into state.

    If reviewer feedback scoped this run away from `node`, skip the model call
    entirely and reuse the previous version's output — that's the whole point
    of scoping: don't spend a call (and don't dilute that node's prompt with
    feedback about a different part of the content) on something the reviewer
    didn't ask to change.

    Any `LLMError` propagates: it fails the run rather than degrading it.
    """
    carried = _carried_forward_payload(state, node)
    if carried is not None:
        _log(state, f"{node}: carried forward, outside this rejection's feedback scope")
        return {node: carried, "sources": {node: SOURCE_CARRIED}, "warnings": []}

    system, user = prompt_builder(state)
    result: LLMResult = generate_json(node=node, system=system, user=user, validator=validator)

    payload = dict(result.payload)
    payload["_source"] = SOURCE_LLM

    warnings: list[str] = []
    if result.repairs:
        # The output is valid — it just took the model more than one go. Worth
        # recording (a node that always needs two attempts means the prompt or
        # the brand rules need attention) but not worth alarming a reviewer.
        warnings.append(f"{node}: needed {result.attempts} attempts ({result.repairs[-1]})")
        _log(state, warnings[-1], level="WARNING")
    else:
        _log(state, f"{node}: generated")

    return {node: payload, "sources": {node: SOURCE_LLM}, "warnings": warnings}


def _load_revision_context(product_id: int) -> Optional[dict[str, Any]]:
    """Everything a run needs to revise from a rejection: the feedback text, the
    previous copy (for the prompt), the scope the reviewer targeted, and the
    full per-node payloads (for carrying unscoped nodes forward unchanged).

    Only the *most recent* version counts. An older rejection that has already
    been answered by a newer version is finished business — applying it again
    would make every future run for this product keep rewriting to feedback the
    reviewer gave once, months ago, and already got a response to.
    """
    versions = list_versions_for_product(product_id)
    if not versions:
        return None
    latest = versions[0]
    if latest.status != "Rejected":
        return None

    meta_path = Path(latest.output_dir) / META_FILENAME
    content: dict[str, Any] = {}
    if meta_path.exists():
        try:
            content = json.loads(meta_path.read_text(encoding="utf-8")).get("content", {})
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read previous version meta at %s: %s", meta_path, exc)

    # Only the copy is useful as revision context; file paths and render stats
    # would just be prompt noise.
    trimmed = {key: content.get(key) for key in NODE_KEYS if content.get(key)}

    selected = {part.strip() for part in (latest.feedback_scope or "").split(",") if part.strip()}
    return {
        "feedback": latest.reviewer_feedback,
        "previous": trimmed,
        "scope": _expand_scope(selected),  # None = every node regenerates
        "carry_forward": content,          # full per-node payloads, for out-of-scope nodes
    }


def discard_orphan_version_dirs(product_id: int) -> list[Path]:
    """Delete `v<N>/` directories with no `versions` row behind them.

    `finalize` creates the DB row only once every artifact is on disk, so a run
    that dies earlier leaves a half-populated directory that nothing points at.
    Clearing them on the next failure keeps the output tree honest — every
    directory there corresponds to a version a reviewer can actually open.
    """
    product = get_product(product_id)
    if product is None or not product.output_dir:
        return []
    root = Path(product.output_dir)
    if not root.is_dir():
        return []

    known = {Path(version.output_dir).name for version in list_versions_for_product(product_id)}
    removed: list[Path] = []
    for child in root.iterdir():
        if child.is_dir() and child.name.startswith("v") and child.name not in known:
            shutil.rmtree(child, ignore_errors=True)
            removed.append(child)
            logger.info("Removed incomplete version directory %s", child)
    return removed


# --- nodes -------------------------------------------------------------------

def load_context(state: PipelineState) -> dict[str, Any]:
    """Fetch product + scraped data, reserve a version directory.

    This is also the gate: without scraped data there is nothing truthful to
    generate from, so the run fails here rather than inventing a product.
    """
    product_id = state["product_id"]
    product = get_product(product_id)
    if product is None:
        return {"failed": True, "failure_reason": f"No product with id {product_id}"}

    scraped = get_scraped_data(product_id)
    if scraped is None:
        return {
            "failed": True,
            "failure_reason": (
                f"Product {product_id} has no scraped_data. Run the scraper first "
                "(the agents may only use scraped facts)."
            ),
        }

    # The `versions` row is not created here — `finalize` creates it once there
    # is something to review. A run that dies mid-way leaves a Failed job and a
    # directory that the next run's cleanup removes, rather than an empty
    # version row staring at a reviewer.
    version_number = next_version_number(product_id)
    output_dir = Path(product.output_dir) / f"v{version_number}"
    output_dir.mkdir(parents=True, exist_ok=True)

    revision = _load_revision_context(product_id)
    if revision and not (revision["feedback"] or revision["previous"]):
        revision = None
    if revision:
        scope = revision["scope"]
        scope_desc = "all nodes" if scope is None else ", ".join(sorted(scope))
        _log(state, f"v{version_number}: revising with reviewer feedback (scope: {scope_desc})")

    _log(state, f"Pipeline started for v{version_number}")
    return {
        "product": {"id": product.id, "name": product.name, "url": product.url},
        "scraped": {
            "title": scraped.title,
            "description_text": scraped.description_text,
            "price": scraped.price,
            "compare_at_price": scraped.compare_at_price,
            "image_urls": scraped.image_urls,
            "specs": scraped.specs,
        },
        "version_number": version_number,
        "output_dir": str(output_dir),
        "revision": revision,
        "failed": False,
    }


def campaign_brief(state: PipelineState) -> dict[str, Any]:
    return _run_agent(
        state,
        node="campaign_brief",
        prompt_builder=prompts.campaign_brief_prompt,
        validator=schemas.campaign_brief,
    )


def script(state: PipelineState) -> dict[str, Any]:
    return _run_agent(
        state,
        node="script",
        prompt_builder=prompts.script_prompt,
        validator=schemas.script,
    )


def caption(state: PipelineState) -> dict[str, Any]:
    return _run_agent(
        state,
        node="caption",
        prompt_builder=prompts.caption_prompt,
        validator=schemas.caption,
    )


def hashtags(state: PipelineState) -> dict[str, Any]:
    return _run_agent(
        state,
        node="hashtags",
        prompt_builder=prompts.hashtags_prompt,
        validator=schemas.hashtags,
    )


def video_plan(state: PipelineState) -> dict[str, Any]:
    # The plan references images by index and scenes by beat, so its validator
    # needs to know how many images exist and what the script's beats were.
    validator = functools.partial(
        schemas.video_plan,
        image_count=len(state["scraped"].get("image_urls") or []),
        beats=[beat["beat"] for beat in state["script"]["beats"]],
    )
    return _run_agent(
        state,
        node="video_plan",
        prompt_builder=prompts.video_plan_prompt,
        validator=validator,
    )


def voiceover(state: PipelineState) -> dict[str, Any]:
    """Produce the narration track. See media/voice.py for the engine chain."""
    path = Path(state["output_dir"]) / "voiceover.wav"
    result = voice.generate_voiceover(state["script"], path)
    _log(
        state,
        f"voiceover: {result.engine}, {result.duration_seconds:.1f}s",
        level="WARNING" if result.is_silent else "INFO",
    )
    for warning in result.warnings:
        _log(state, f"voiceover warning: {warning}", level="WARNING")

    return {
        "voiceover": result.as_dict(),
        "artifacts": [
            {"output_type": "voiceover", "file_path": str(result.path), "source": result.engine}
        ],
        "sources": {"voiceover": result.engine},
        "warnings": list(result.warnings),
    }


def render_video(state: PipelineState) -> dict[str, Any]:
    """Render the MP4.

    Unlike the copy nodes, a render failure degrades the version rather than
    killing it: the brief, script, caption and hashtags are all real, complete
    and reviewable without it, and every one of them would have to be
    regenerated (and paid for again) to recover from an ffmpeg hiccup.
    """
    path = Path(state["output_dir"]) / "video.mp4"
    voiceover_path = Path(state["voiceover"]["file_path"]) if state.get("voiceover") else None

    try:
        result = movie.render_video(
            video_plan=state["video_plan"],
            image_urls=state["scraped"].get("image_urls") or [],
            output_path=path,
            voiceover_path=voiceover_path,
        )
    except Exception as exc:  # noqa: BLE001 — the other artifacts are still valid
        message = f"video render failed: {type(exc).__name__}: {exc}"
        logger.exception("Video render failed")
        _log(state, message, level="ERROR")
        return {"video": {"error": message}, "warnings": [message], "sources": {"video": "failed"}}

    _log(state, f"video: {result.duration_seconds:.1f}s, {result.scene_count} scenes")
    for warning in result.warnings:
        _log(state, f"video warning: {warning}", level="WARNING")

    return {
        "video": result.as_dict(),
        "artifacts": [{"output_type": "video", "file_path": str(result.path), "source": "render"}],
        "sources": {"video": "render"},
        "warnings": list(result.warnings),
    }


def finalize(state: PipelineState) -> dict[str, Any]:
    """Write the text artifacts, register every output row, hand over to review."""
    output_dir = Path(state["output_dir"])
    written: list[dict[str, str]] = []

    def write(name: str, text: str, output_type: str, source: str) -> None:
        path = output_dir / name
        path.write_text(text, encoding="utf-8")
        written.append({"output_type": output_type, "file_path": str(path), "source": source})

    brief = state["campaign_brief"]
    write("campaign_brief.md", _render_brief_markdown(brief), "campaign_brief", brief["_source"])
    _write_json(output_dir / "campaign_brief.json", brief)

    script_payload = state["script"]
    write("script.md", _render_script_markdown(script_payload), "script", script_payload["_source"])
    _write_json(output_dir / "script.json", script_payload)

    caption_payload = state["caption"]
    write("caption.txt", caption_payload["caption"], "caption", caption_payload["_source"])

    hashtag_payload = state["hashtags"]
    write(
        "hashtags.txt",
        " ".join(hashtag_payload["hashtags"]),
        "hashtags",
        hashtag_payload["_source"],
    )

    plan = state["video_plan"]
    write(
        "video_plan.json",
        json.dumps(plan, indent=2, ensure_ascii=False),
        "video_plan",
        plan["_source"],
    )

    # Everything is on disk and valid — only now does a reviewable version exist.
    version = create_version(state["product_id"], state.get("job_id"))
    if version.version_number != state["version_number"]:
        # Single-worker model means this shouldn't happen; if it ever does, the
        # files are in the directory named by the number we reserved.
        logger.warning(
            "Version number moved from v%s to v%s between planning and finalize; "
            "artifacts are in %s",
            state["version_number"], version.version_number, output_dir,
        )

    # Media nodes already produced their files; they only need registering.
    all_artifacts = written + list(state.get("artifacts") or [])
    for artifact in all_artifacts:
        add_output(version.id, artifact["output_type"], artifact["file_path"])

    config = active_config()
    meta = {
        "product_id": state["product_id"],
        "job_id": state.get("job_id"),
        "version_id": version.id,
        "version_number": version.version_number,
        "provider": config.name,
        "model": config.model,
        "sources": dict(state.get("sources") or {}),
        "warnings": list(state.get("warnings") or []),
        "revision_of_feedback": (state.get("revision") or {}).get("feedback"),
        "content": {
            "campaign_brief": brief,
            "script": script_payload,
            "caption": caption_payload,
            "hashtags": hashtag_payload,
            "video_plan": plan,
            "voiceover": state.get("voiceover"),
            "video": state.get("video"),
        },
    }
    _write_json(output_dir / META_FILENAME, meta)

    update_product_status(state["product_id"], "Review")
    _log(state, f"v{version.version_number} ready for review ({len(all_artifacts)} artifacts)")
    return {"version_id": version.id, "version_number": version.version_number, "artifacts": written}


def _write_json(path: Path, payload: Any) -> None:
    path.write_text(json.dumps(payload, indent=2, ensure_ascii=False), encoding="utf-8")


# --- artifact formatting -----------------------------------------------------

def _render_brief_markdown(brief: dict[str, Any]) -> str:
    persona_id = brief.get("target_persona", "")
    persona = load_brand().persona(persona_id)
    persona_line = f"{persona_id} — {persona['name']}" if persona else persona_id

    lines = [
        "# Campaign Brief",
        "",
        f"**Objective** — {brief.get('objective', '')}",
        "",
        f"**Target persona** — {persona_line}",
    ]
    if brief.get("persona_rationale"):
        lines.append(f"  \n_{brief['persona_rationale']}_")
    lines += ["", f"**Key message** — {brief.get('key_message', '')}", "", "## Proof points", ""]
    for point in brief.get("proof_points") or []:
        lines.append(f"- {point.get('claim', '')}  \n  _source: {point.get('source', '')}_")
    lines += [
        "",
        f"**Channels** — {', '.join(brief.get('channels') or [])}",
        "",
        f"**Success metric** — {brief.get('success_metric', '')}",
    ]
    return "\n".join(lines) + "\n"


def _render_script_markdown(script_payload: dict[str, Any]) -> str:
    lines = [
        f"# {script_payload.get('title', 'Script')}",
        "",
        f"_Estimated spoken duration: {script_payload.get('estimated_duration_seconds', '?')}s "
        f"({script_payload.get('word_count', '?')} words)_",
        "",
    ]
    for beat in script_payload.get("beats") or []:
        lines.append(f"### {beat.get('beat', '')}")
        lines.append("")
        lines.append(beat.get("line", ""))
        if beat.get("on_screen"):
            lines.append(f"  \n`on screen: {beat['on_screen']}`")
        lines.append("")
    return "\n".join(lines)
