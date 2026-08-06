"""Background worker: polls the jobs queue and runs the full pipeline per product.

Usage (from project root):
    python -m worker.run

Long-lived process. A job now means: scrape the product, then run the LangGraph
content pipeline over the scraped data to produce a complete, reviewable version
(brief, script, caption, hashtags, voiceover, video plan, rendered video).
Ctrl+C exits cleanly.
"""
from __future__ import annotations

import logging
import time

from config.settings import WORKER_POLL_INTERVAL_SECONDS
from database.connection import init_db
from database.models import Job
from database.repository import (
    add_log,
    get_job,
    get_next_pending_job,
    is_cancel_requested,
    reclaim_stale_jobs,
    update_job_status,
    update_job_stage,
    update_product_status,
)
from graph.pipeline import PipelineCancelled, PipelineError, run_pipeline
from scraper.radboards import ScrapeError
from scraper.run import scrape_and_store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def process_job(job: Job) -> None:
    logger.info("Job %s: starting for product %s", job.id, job.product_id)
    update_job_status(job.id, "Running")
    update_product_status(job.product_id, "Running")
    add_log("Job started", product_id=job.product_id, job_id=job.id)

    if is_cancel_requested(job.id):
        _cancel(job)
        return

    update_job_stage(job.id, "scrape")
    try:
        scrape_and_store(job.product_id, job_id=job.id)
    except (ScrapeError, ValueError) as exc:
        _fail(job, f"Scrape failed: {exc}")
        return

    try:
        result = run_pipeline(job.product_id, job_id=job.id)

        # The pipeline's finalize node leaves the product in `Review` — there is
        # now generated content waiting on a human, which is the whole point of
        # the run. Marking the job Completed must happen in the same try block:
        # any failure here (e.g. a transient DB lock) must still resolve the job
        # to Failed rather than leaving it stuck in Running forever.
        update_job_status(job.id, "Completed")
        summary = f"Job completed: v{result['version_number']} with {result['artifact_count']} artifacts"
        if result["stubbed_nodes"]:
            summary += f" (stub content for: {', '.join(result['stubbed_nodes'])})"
        add_log(summary, product_id=job.product_id, job_id=job.id)
        logger.info("Job %s: %s", job.id, summary)
    except PipelineCancelled:
        _cancel(job)
    except PipelineError as exc:
        _fail(job, f"Pipeline failed: {exc}")
    except Exception as exc:  # noqa: BLE001 — an unexpected crash must not kill the worker
        logger.exception("Job %s: unexpected pipeline error", job.id)
        _fail(job, f"Unexpected pipeline error: {type(exc).__name__}: {exc}")


def _fail(job: Job, message: str) -> None:
    # current_stage was last set (by update_job_stage, above and inside
    # graph/pipeline.py's _tracked wrapper) to whichever node was running when
    # this failure happened — re-fetch since `job` was loaded before the run
    # started and won't reflect it.
    fresh = get_job(job.id)
    stage = fresh.current_stage if fresh else None
    full_message = f"[{stage}] {message}" if stage else message
    logger.error("Job %s: %s", job.id, full_message)
    update_job_status(job.id, "Failed", error_message=full_message)
    update_product_status(job.product_id, "Failed")
    add_log(f"Job failed: {full_message}", product_id=job.product_id, job_id=job.id, level="ERROR")


def _cancel(job: Job) -> None:
    logger.info("Job %s: cancelled", job.id)
    update_job_status(job.id, "Cancelled")
    update_product_status(job.product_id, "Cancelled")
    add_log("Job cancelled by reviewer", product_id=job.product_id, job_id=job.id, level="WARNING")


def main() -> None:
    init_db()
    reclaimed_products = reclaim_stale_jobs()
    for product_id in reclaimed_products:
        update_product_status(product_id, "Failed")
    if reclaimed_products:
        logger.warning(
            "Reclaimed %d job(s) orphaned by a previous worker shutdown", len(reclaimed_products)
        )
    logger.info("Worker started, polling every %ss", WORKER_POLL_INTERVAL_SECONDS)
    try:
        while True:
            job = get_next_pending_job()
            if job is None:
                time.sleep(WORKER_POLL_INTERVAL_SECONDS)
                continue
            try:
                process_job(job)
            except Exception:  # noqa: BLE001 — one bad job must not kill the poll loop
                logger.exception("Job %s: crashed outside process_job's own handling", job.id)
                try:
                    _fail(job, "Worker crashed while handling this job")
                except Exception:  # noqa: BLE001 — DB itself may be the thing that's down
                    logger.exception("Job %s: could not even mark as Failed", job.id)
    except KeyboardInterrupt:
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
