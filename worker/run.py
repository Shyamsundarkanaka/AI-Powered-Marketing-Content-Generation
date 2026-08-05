"""Background worker: polls the jobs queue and runs the pipeline for each product.

Usage (from project root):
    python -m worker.run

Long-lived process. Today a job only scrapes the product (no AI agents
exist yet); later pipeline stages will be added to `process_job` as they
land. Ctrl+C exits cleanly.
"""
from __future__ import annotations

import logging
import time

from config.settings import WORKER_POLL_INTERVAL_SECONDS
from database.connection import init_db
from database.models import Job
from database.repository import (
    add_log,
    get_next_pending_job,
    update_job_status,
    update_product_status,
)
from scraper.radboards import ScrapeError
from scraper.run import scrape_and_store

logging.basicConfig(level=logging.INFO, format="%(levelname)s %(name)s: %(message)s")
logger = logging.getLogger(__name__)


def process_job(job: Job) -> None:
    logger.info("Job %s: starting for product %s", job.id, job.product_id)
    update_job_status(job.id, "Running")
    update_product_status(job.product_id, "Running")
    add_log("Job started", product_id=job.product_id, job_id=job.id)

    try:
        scrape_and_store(job.product_id, job_id=job.id)
    except (ScrapeError, ValueError) as exc:
        logger.error("Job %s: failed: %s", job.id, exc)
        update_job_status(job.id, "Failed", error_message=str(exc))
        update_product_status(job.product_id, "Failed")
        add_log(f"Job failed: {exc}", product_id=job.product_id, job_id=job.id, level="ERROR")
        return

    update_job_status(job.id, "Completed")
    update_product_status(job.product_id, "Pending")
    add_log("Job completed", product_id=job.product_id, job_id=job.id)
    logger.info("Job %s: completed for product %s", job.id, job.product_id)


def main() -> None:
    init_db()
    logger.info("Worker started, polling every %ss", WORKER_POLL_INTERVAL_SECONDS)
    try:
        while True:
            job = get_next_pending_job()
            if job is None:
                time.sleep(WORKER_POLL_INTERVAL_SECONDS)
                continue
            process_job(job)
    except KeyboardInterrupt:
        logger.info("Worker stopped")


if __name__ == "__main__":
    main()
