"""Shared HTTP session: identifies itself, retries politely, decodes gzip/brotli."""

from __future__ import annotations

import requests
from requests.adapters import HTTPAdapter
from urllib3.util.retry import Retry

USER_AGENT = "ncaambb-composite/0.1 (personal non-commercial ratings dashboard)"
TIMEOUT_SECONDS = 30

# Markers of anti-bot interstitials that some sites return with HTTP 200.
BOT_CHECK_MARKERS = (
    "Verifying your browser",
    "Just a moment...",
    "Vercel Security Checkpoint",
    "Enable JavaScript and cookies",
)


class FetchError(RuntimeError):
    """Raised when a source cannot be downloaded or returns a bot-check page."""


class NotConfigured(RuntimeError):
    """Raised when a source needs setup (e.g. an API key) that is missing."""


def make_session() -> requests.Session:
    session = requests.Session()
    session.headers.update({"User-Agent": USER_AGENT})
    retry = Retry(
        total=3,
        backoff_factor=2,
        status_forcelist=(429, 500, 502, 503, 504),
        allowed_methods=("GET",),
    )
    session.mount("https://", HTTPAdapter(max_retries=retry))
    return session


def fetch_bytes(
    url: str,
    session: requests.Session | None = None,
    headers: dict[str, str] | None = None,
) -> bytes:
    """GET a URL and return the decoded body, or raise FetchError."""
    session = session or make_session()
    try:
        resp = session.get(url, timeout=TIMEOUT_SECONDS, headers=headers)
        resp.raise_for_status()
    except requests.RequestException as exc:
        raise FetchError(f"{url}: {exc}") from exc
    head = resp.content[:4000].decode("utf-8", errors="ignore")
    for marker in BOT_CHECK_MARKERS:
        if marker in head:
            raise FetchError(f"{url}: blocked by bot check ({marker!r})")
    return resp.content
