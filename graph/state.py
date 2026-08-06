"""The state object threaded through every node of the pipeline graph.

LangGraph merges each node's returned dict into this state. Keys that more than
one node writes concurrently need an explicit reducer — `artifacts`, `warnings`
and `sources` are written by the parallel caption/hashtags/video_plan branch, so
they carry `Annotated[..., reducer]`. Everything else is written by exactly one
node and uses last-write-wins.

Note what is *not* here: there is no per-node error field. A copy node either
produces valid content or raises, which fails the whole run. `warnings` carries
only non-fatal notes — a silent voiceover, a render that fell back, a node that
needed a second attempt — all of which still leave a reviewable version.
"""
from __future__ import annotations

import operator
from typing import Annotated, Any, Optional, TypedDict


def merge_sources(left: dict[str, str], right: dict[str, str]) -> dict[str, str]:
    """Reducer for the per-node provenance map (`llm`, `carried_forward`, …)."""
    return {**left, **right}


class Artifact(TypedDict):
    """One row destined for the `outputs` table, plus what produced it."""

    output_type: str   # one of database.models.OUTPUT_TYPES
    file_path: str
    source: str        # "llm" | "carried_forward" | "render" | a TTS engine name


class PipelineState(TypedDict, total=False):
    # --- inputs, set before the graph runs ---
    product_id: int
    job_id: Optional[int]

    # --- established by load_context ---
    product: dict[str, Any]
    scraped: dict[str, Any]
    version_id: int
    version_number: int
    output_dir: str
    revision: Optional[dict[str, Any]]   # {"feedback": str, "previous": {...}}

    # --- generated content, one key per agent ---
    campaign_brief: dict[str, Any]
    script: dict[str, Any]
    caption: dict[str, Any]
    hashtags: dict[str, Any]
    video_plan: dict[str, Any]
    voiceover: dict[str, Any]
    video: dict[str, Any]

    # --- accumulated across nodes (need reducers) ---
    artifacts: Annotated[list[Artifact], operator.add]
    warnings: Annotated[list[str], operator.add]
    sources: Annotated[dict[str, str], merge_sources]

    # --- terminal ---
    failed: bool
    failure_reason: str


def new_state(product_id: int, job_id: Optional[int]) -> PipelineState:
    """Initial state. The accumulator keys must start empty, not absent."""
    return PipelineState(
        product_id=product_id,
        job_id=job_id,
        artifacts=[],
        warnings=[],
        sources={},
        failed=False,
    )
