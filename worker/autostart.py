"""Runs the worker loop as a background thread inside the Streamlit process.

`python -m worker.run` as a separate long-lived process is still the
production shape (see its own docstring), but for the local/demo app a
second terminal that's easy to forget or let die is just a footgun: a job
queued while no worker is alive sits `Pending` forever, which permanently
disables every "Run" button (the dashboard treats a queued job as "wait for
it"). `ensure_worker_running()` makes the Streamlit app self-sufficient by
starting that same loop, once, on a daemon thread the first time any page
loads.
"""
from __future__ import annotations

import logging
import threading

logger = logging.getLogger(__name__)

_thread: threading.Thread | None = None
_lock = threading.Lock()


def ensure_worker_running() -> None:
    global _thread
    with _lock:
        if _thread is not None and _thread.is_alive():
            return

        from worker.run import main as worker_main

        _thread = threading.Thread(target=worker_main, name="pipeline-worker", daemon=True)
        _thread.start()
        logger.info("Started background worker thread.")
