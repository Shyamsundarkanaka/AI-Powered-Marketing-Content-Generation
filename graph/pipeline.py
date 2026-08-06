"""Graph topology and the entry point the worker calls.

    load_context
         │  (fails fast if the product has no scraped data)
    campaign_brief
         │
       script
      ╱   │   ╲            three independent agents, run in one superstep
 caption hashtags video_plan
      ╲   │   ╱
     voiceover              needs the script; joins the fan-out
         │
    render_video            needs the plan and the audio
         │
      finalize              writes files, registers outputs, opens review

The fan-out is real parallelism in LangGraph terms — the three branches are
dispatched together and `voiceover` waits for all of them. It works because
those nodes write disjoint state keys, and the keys they *share*
(`artifacts`, `errors`, `sources`) carry reducers in `graph/state.py`.
"""
from __future__ import annotations

import logging
from typing import Any, Callable, Optional

from langgraph.graph import END, START, StateGraph

from database.repository import is_cancel_requested, update_job_stage
from graph import nodes
from graph.state import PipelineState, new_state

logger = logging.getLogger(__name__)


class PipelineCancelled(RuntimeError):
    """Raised when a cancel was requested at a stage boundary; unwinds the run."""


def _after_context(state: PipelineState) -> str:
    """Stop the run if load_context could not establish a usable product."""
    return "abort" if state.get("failed") else "continue"


def _tracked(name: str, fn: Callable[[PipelineState], dict]) -> Callable[[PipelineState], dict]:
    """Record the current stage and honour cancellation at the node boundary.

    Cancellation is cooperative: it is only checked between nodes, so a run is
    never interrupted mid-stage — a cancel lands within one stage's duration.
    """

    def wrapped(state: PipelineState) -> dict:
        job_id = state.get("job_id")
        if job_id is not None:
            if is_cancel_requested(job_id):
                raise PipelineCancelled(f"Cancelled before stage '{name}'")
            update_job_stage(job_id, name)
        return fn(state)

    wrapped.__name__ = f"tracked_{name}"
    return wrapped


def build_graph():
    """Assemble and compile the pipeline graph."""
    builder = StateGraph(PipelineState)

    builder.add_node("load_context", _tracked("load_context", nodes.load_context))
    builder.add_node("campaign_brief", _tracked("campaign_brief", nodes.campaign_brief))
    builder.add_node("script", _tracked("script", nodes.script))
    builder.add_node("caption", _tracked("caption", nodes.caption))
    builder.add_node("hashtags", _tracked("hashtags", nodes.hashtags))
    builder.add_node("video_plan", _tracked("video_plan", nodes.video_plan))
    builder.add_node("voiceover", _tracked("voiceover", nodes.voiceover))
    builder.add_node("render_video", _tracked("render_video", nodes.render_video))
    builder.add_node("finalize", _tracked("finalize", nodes.finalize))

    builder.add_edge(START, "load_context")
    builder.add_conditional_edges(
        "load_context",
        _after_context,
        {"continue": "campaign_brief", "abort": END},
    )
    builder.add_edge("campaign_brief", "script")

    for branch in ("caption", "hashtags", "video_plan"):
        builder.add_edge("script", branch)
        builder.add_edge(branch, "voiceover")

    builder.add_edge("voiceover", "render_video")
    builder.add_edge("render_video", "finalize")
    builder.add_edge("finalize", END)

    return builder.compile()


class PipelineError(RuntimeError):
    """The run could not produce a version at all (as opposed to degrading)."""


def run_pipeline(product_id: int, job_id: Optional[int] = None) -> dict[str, Any]:
    """Generate one complete content version for a product.

    Raises `PipelineError` only when nothing could be produced — a missing
    product or missing scraped data. Individual node failures (no API key, a
    render error) degrade the version instead: the run still finishes, the
    artifacts still exist, and the provenance says what happened.
    """
    graph = build_graph()
    logger.info("Running content pipeline for product %s (job %s)", product_id, job_id)

    # recursion_limit is LangGraph's superstep cap; this graph is a DAG with a
    # fixed depth of 7, so the default would do — it is set explicitly so a
    # future cycle (e.g. a self-critique loop) fails loudly rather than hanging.
    final_state: PipelineState = graph.invoke(
        new_state(product_id, job_id), config={"recursion_limit": 25}
    )

    if final_state.get("failed"):
        raise PipelineError(final_state.get("failure_reason", "pipeline failed"))

    sources = final_state.get("sources") or {}
    stubbed = sorted(node for node, source in sources.items() if source == "stub")
    if stubbed:
        logger.warning(
            "v%s produced with stub content for: %s",
            final_state.get("version_number"),
            ", ".join(stubbed),
        )

    return {
        "version_id": final_state["version_id"],
        "version_number": final_state["version_number"],
        "output_dir": final_state["output_dir"],
        "artifact_count": len(final_state.get("artifacts") or []),
        "sources": sources,
        "stubbed_nodes": stubbed,
        "errors": final_state.get("errors") or [],
    }


def main() -> None:
    """Run the pipeline for one product without the worker: `python -m graph.pipeline 5`."""
    import argparse

    from database.connection import init_db

    parser = argparse.ArgumentParser(description="Run the content pipeline for one product.")
    parser.add_argument("product_id", type=int)
    args = parser.parse_args()

    logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
    init_db()
    result = run_pipeline(args.product_id)
    print(
        f"v{result['version_number']} -> {result['output_dir']} "
        f"({result['artifact_count']} artifacts)"
    )
    if result["stubbed_nodes"]:
        print(f"  stubbed: {', '.join(result['stubbed_nodes'])}")


if __name__ == "__main__":
    main()
