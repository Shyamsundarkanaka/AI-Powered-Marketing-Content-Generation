"""LangGraph content-generation pipeline.

The worker calls `run_pipeline(product_id, job_id)`. Everything else in this
package is an implementation detail of the graph: state shape, node functions,
prompts, the LLM client and its stub fallback.

Nothing here touches Streamlit, and Streamlit never imports this package —
inference happens only in the worker process.
"""
from graph.pipeline import build_graph, run_pipeline

__all__ = ["build_graph", "run_pipeline"]
