"""LangGraph content-generation pipeline.

The worker calls `graph.pipeline.run_pipeline(product_id, job_id)`. Everything
else in this package is an implementation detail of the graph: state shape, node
functions, prompts, response schemas and the LLM client.

Deliberately empty of imports. Re-exporting `run_pipeline` here would drag
langgraph, the provider clients, moviepy and Pillow into the process for anyone
who so much as touches `graph.schemas` — and it makes `python -m graph.pipeline`
emit a "found in sys.modules" warning, because the package import runs the
module before runpy does.
"""
