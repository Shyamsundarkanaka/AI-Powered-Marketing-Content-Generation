"""The node functions that make up the pipeline graph.

Each node is a plain `PipelineState -> dict` function: it reads what it needs
from state and returns only the keys it writes, which LangGraph merges. Nothing
here constructs the graph — that is `pipeline.py`'s job — so nodes stay
individually callable and testable.

Every agent node follows the same contract via `_run_agent()`: build a prompt,
ask the LLM, fall back to the node's stub on any failure, and record the
provenance under `sources[node]`.
"""
from __future__ import annotations

import json
import logging
from pathlib import Path
from typing import Any, Callable

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
from graph import prompts, stubs
from graph.llm import SOURCE_STUB, generate_json
from graph.state import PipelineState
from media import movie, voice

logger = logging.getLogger(__name__)

META_FILENAME = "_meta.json"


# --- shared helpers ----------------------------------------------------------

def _log(state: PipelineState, message: str, level: str = "INFO") -> None:
    add_log(message, product_id=state.get("product_id"), job_id=state.get("job_id"), level=level)


def _run_agent(
    state: PipelineState,
    *,
    node: str,
    state_key: str,
    prompt_builder: Callable[[dict[str, Any]], tuple[str, str]],
    required_keys: tuple[str, ...],
    stub_factory: Callable[[dict[str, Any]], dict[str, Any]],
) -> dict[str, Any]:
    """Run one generation agent and normalise the result into state."""
    system, user = prompt_builder(state)
    payload, source, error = generate_json(
        node=node,
        system=system,
        user=user,
        required_keys=required_keys,
        stub_factory=lambda: stub_factory(state),
    )
    payload = dict(payload)
    payload["_source"] = source

    if source == SOURCE_STUB:
        _log(state, f"{node}: LLM unavailable, wrote stub output ({error})", level="WARNING")
    else:
        _log(state, f"{node}: generated")

    return {
        state_key: payload,
        "sources": {node: source},
        "errors": [f"{node}: {error}"] if error else [],
    }


def _previous_version_content(product_id: int) -> tuple[str | None, dict[str, Any]]:
    """Reviewer feedback and generated content from the most recent rejection.

    Returns `("", {})` when there is nothing to revise. Reading the previous
    output back off disk (rather than keeping it in memory) is what lets a
    rejection from last week feed a run started today.
    """
    versions = list_versions_for_product(product_id)
    rejected = next((v for v in versions if v.status == "Rejected"), None)
    if rejected is None:
        return None, {}

    meta_path = Path(rejected.output_dir) / META_FILENAME
    content: dict[str, Any] = {}
    if meta_path.exists():
        try:
            content = json.loads(meta_path.read_text(encoding="utf-8")).get("content", {})
        except (OSError, json.JSONDecodeError) as exc:
            logger.warning("Could not read previous version meta at %s: %s", meta_path, exc)

    # Only the copy is useful as revision context; file paths and render stats
    # would just be prompt noise.
    trimmed = {
        key: content.get(key)
        for key in ("campaign_brief", "script", "caption", "hashtags")
        if content.get(key)
    }
    return rejected.reviewer_feedback, trimmed


# --- nodes -------------------------------------------------------------------

def load_context(state: PipelineState) -> dict[str, Any]:
    """Fetch product + scraped data, open a new version, prepare its directory.

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

    feedback, previous = _previous_version_content(product_id)

    # The `versions` row is not created here — `finalize` creates it once there
    # is something to review. A run that dies mid-way leaves files on disk (and
    # a Failed job) rather than an empty version row in `Review`.
    version_number = next_version_number(product_id)
    output_dir = Path(product.output_dir) / f"v{version_number}"
    output_dir.mkdir(parents=True, exist_ok=True)

    revision = {"feedback": feedback, "previous": previous} if feedback or previous else None
    if revision:
        _log(state, f"v{version_number}: revising with reviewer feedback")

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
        state_key="campaign_brief",
        prompt_builder=prompts.campaign_brief_prompt,
        required_keys=prompts.CAMPAIGN_BRIEF_KEYS,
        stub_factory=stubs.stub_campaign_brief,
    )


def script(state: PipelineState) -> dict[str, Any]:
    return _run_agent(
        state,
        node="script",
        state_key="script",
        prompt_builder=prompts.script_prompt,
        required_keys=prompts.SCRIPT_KEYS,
        stub_factory=stubs.stub_script,
    )


def caption(state: PipelineState) -> dict[str, Any]:
    return _run_agent(
        state,
        node="caption",
        state_key="caption",
        prompt_builder=prompts.caption_prompt,
        required_keys=prompts.CAPTION_KEYS,
        stub_factory=stubs.stub_caption,
    )


def hashtags(state: PipelineState) -> dict[str, Any]:
    return _run_agent(
        state,
        node="hashtags",
        state_key="hashtags",
        prompt_builder=prompts.hashtags_prompt,
        required_keys=prompts.HASHTAG_KEYS,
        stub_factory=stubs.stub_hashtags,
    )


def video_plan(state: PipelineState) -> dict[str, Any]:
    return _run_agent(
        state,
        node="video_plan",
        state_key="video_plan",
        prompt_builder=prompts.video_plan_prompt,
        required_keys=prompts.VIDEO_PLAN_KEYS,
        stub_factory=stubs.stub_video_plan,
    )


def voiceover(state: PipelineState) -> dict[str, Any]:
    """Produce the narration track (silence by default — see media/voice.py)."""
    path = Path(state["output_dir"]) / "voiceover.wav"
    result = voice.generate_voiceover(state["script"], path)
    _log(state, f"voiceover: {result.kind}, {result.duration_seconds:.1f}s")
    return {
        "voiceover": result.as_dict(),
        "artifacts": [
            {"output_type": "voiceover", "file_path": str(result.path), "source": result.kind}
        ],
        "sources": {"voiceover": result.kind},
    }


def render_video(state: PipelineState) -> dict[str, Any]:
    """Render the MP4. A render failure degrades the version, it does not kill it."""
    path = Path(state["output_dir"]) / "video.mp4"
    voiceover_path = Path(state["voiceover"]["file_path"]) if state.get("voiceover") else None

    try:
        result = movie.render_video(
            video_plan=state["video_plan"],
            image_urls=state["scraped"].get("image_urls") or [],
            output_path=path,
            voiceover_path=voiceover_path,
        )
    except Exception as exc:  # noqa: BLE001 — the other six artifacts are still valid
        message = f"video render failed: {type(exc).__name__}: {exc}"
        logger.exception("Video render failed")
        _log(state, message, level="ERROR")
        return {"video": {"error": message}, "errors": [message], "sources": {"video": "failed"}}

    _log(state, f"video: {result.duration_seconds:.1f}s, {result.scene_count} scenes")
    for warning in result.warnings:
        _log(state, f"video warning: {warning}", level="WARNING")

    return {
        "video": result.as_dict(),
        "artifacts": [{"output_type": "video", "file_path": str(result.path), "source": "render"}],
        "sources": {"video": "render"},
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
    (output_dir / "campaign_brief.json").write_text(
        json.dumps(brief, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    script_payload = state["script"]
    write("script.md", _render_script_markdown(script_payload), "script", script_payload["_source"])
    (output_dir / "script.json").write_text(
        json.dumps(script_payload, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    caption_payload = state["caption"]
    write("caption.txt", caption_payload.get("caption", ""), "caption", caption_payload["_source"])

    hashtag_payload = state["hashtags"]
    write(
        "hashtags.txt",
        " ".join(hashtag_payload.get("hashtags") or []),
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

    sources = dict(state.get("sources") or {})
    meta = {
        "product_id": state["product_id"],
        "job_id": state.get("job_id"),
        "version_id": version.id,
        "version_number": version.version_number,
        "model": _model_name(),
        "sources": sources,
        "stubbed_nodes": sorted(node for node, src in sources.items() if src == SOURCE_STUB),
        "errors": list(state.get("errors") or []),
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
    (output_dir / META_FILENAME).write_text(
        json.dumps(meta, indent=2, ensure_ascii=False), encoding="utf-8"
    )

    update_product_status(state["product_id"], "Review")
    _log(state, f"v{version.version_number} ready for review ({len(all_artifacts)} artifacts)")
    return {"version_id": version.id, "version_number": version.version_number, "artifacts": written}


def _model_name() -> str:
    from config.settings import ANTHROPIC_MODEL

    return ANTHROPIC_MODEL


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
        if isinstance(point, dict):
            lines.append(f"- {point.get('claim', '')}  \n  _source: {point.get('source', '')}_")
        else:
            lines.append(f"- {point}")
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
        f"_Estimated spoken duration: {script_payload.get('estimated_duration_seconds', '?')}s_",
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
