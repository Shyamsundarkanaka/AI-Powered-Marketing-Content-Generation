"""One shared, retrying HTTP session for every outbound request.

Three modules fetch over HTTP — the product scraper, the brand-signal
collector, and the renderer's image library — and each previously called
`requests.get` directly. That meant no connection reuse (a 12-image render
opened 12 TLS connections to the same host) and no retry, so a single dropped
packet during a scrape failed a whole job.

`urllib3`'s `Retry` handles the cases worth retrying — connection errors and
the 429/5xx family — with exponential backoff, and honours `Retry-After`.
Client errors like 404 are *not* retried: a product page that doesn't exist
won't start existing.
"""
from __future__ import annotations

import functools

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

from config.settings import HTTP_MAX_RETRIES

USER_AGENT = "Mozilla/5.0 (compatible; MarketingContentBot/2.0; +https://radboards.in)"

RETRY_STATUSES = (429, 500, 502, 503, 504)


@functools.lru_cache(maxsize=1)
def http_session() -> requests.Session:
    """A process-wide session with connection pooling and retries."""
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})

    retry = Retry(
        total=HTTP_MAX_RETRIES,
        connect=HTTP_MAX_RETRIES,
        read=HTTP_MAX_RETRIES,
        status=HTTP_MAX_RETRIES,
        backoff_factor=0.5,
        status_forcelist=RETRY_STATUSES,
        allowed_methods=frozenset({"GET", "HEAD"}),
        raise_on_status=False,
        respect_retry_after_header=True,
    )
    adapter = HTTPAdapter(max_retries=retry, pool_connections=8, pool_maxsize=16)
    session.mount("https://", adapter)
    session.mount("http://", adapter)
    return session
