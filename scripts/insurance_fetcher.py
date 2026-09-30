"""Shared, bounded, host-paced HTTP fetcher for this project's crawlers.

Concept borrowed from `DirectFetcher` in
C:/Users/rabbi/OneDrive/桌面/final/repo-new_crawler/crawler/owner_crawl/executor.py
(remote YZU1507A/new_crawler) -- three separate timeouts (connect/read/wall),
per-host adaptive pacing driven by the server's own 429/503 + Retry-After
signal, and a small set of STABLE error codes instead of raw exception text
(so a manifest keyed by error code stays useful instead of one row per
distinct message).

What's deliberately NOT carried over from that source: `yzu_contracts`
(`CrawlJob`/`PageArtifact`/etc, a YZU-specific pydantic contract library --
this project has its own shapes, see policy_data_contract.py), `requests`
(this project already depends on `httpx` throughout scripts/sources/
ib_disclosure/*, so this reuses that instead of adding a second HTTP
library), and the raw-socket `sock.settimeout()` trick for wall-timeout
enforcement mid-chunk (httpx doesn't expose the underlying socket the way
urllib3/requests does; this fetcher instead checks the deadline between
each streamed chunk via `response.iter_bytes()`, which is a slightly
coarser but dependency-free approximation of the same guarantee).

This module makes no assumption about *which* crawler uses it -- IB, TII, or
anything future. It does not replace scripts/sources/ib_disclosure/
query_client.py's ASP.NET postback flow (that needs cookies/hidden-field
state this fetcher doesn't model) or download_client.py's two-step
resolve+fetch; it's a plain, general-purpose GET fetcher for anything that
doesn't need that.

Usage:
    fetcher = InsuranceFetcher()
    response = fetcher.get("https://example.gov.tw/some/page")
    if response.error_code:
        ...  # stable code, see FETCH_ERROR_CODES
    else:
        ...  # response.body, response.status_code, response.content_type
"""

from __future__ import annotations

import time
from dataclasses import dataclass, field
from email.utils import parsedate_to_datetime
from typing import Any, Callable
from urllib.parse import urlsplit

import httpx

FETCH_ERROR_CODES = frozenset(
    {
        "FETCH_CONNECT_TIMEOUT",
        "FETCH_READ_TIMEOUT",
        "FETCH_WALL_TIMEOUT",
        "FETCH_CONNECTION_ERROR",
        "FETCH_TLS_ERROR",
        "FETCH_REDIRECT_LIMIT",
        "FETCH_REQUEST_ERROR",
        "BODY_TOO_LARGE",
        "HTTP_429",
        "HTTP_5XX",
    }
)

# 429/5xx are worth a caller retrying later (with backoff); everything else
# here is a fact about the URL/response that retrying won't change.
RETRYABLE_ERROR_CODES = frozenset(
    {
        "FETCH_CONNECT_TIMEOUT",
        "FETCH_READ_TIMEOUT",
        "FETCH_WALL_TIMEOUT",
        "FETCH_CONNECTION_ERROR",
        "HTTP_429",
        "HTTP_5XX",
    }
)

MAX_HOST_DELAY_SECONDS = 30.0


def is_retryable_error(error_code: str | None) -> bool:
    if not error_code:
        return False
    return error_code in RETRYABLE_ERROR_CODES


@dataclass(frozen=True)
class InsuranceFetchResponse:
    requested_url: str
    final_url: str
    status_code: int
    headers: dict[str, str] = field(default_factory=dict)
    body: bytes = b""
    error_code: str | None = None
    elapsed_seconds: float = 0.0

    @property
    def content_type(self) -> str:
        return self.headers.get("content-type", "").split(";", 1)[0].strip().lower()

    @property
    def ok(self) -> bool:
        return self.error_code is None and 200 <= self.status_code < 300


def _retry_after_seconds(headers: dict[str, str]) -> float | None:
    """Retry-After as seconds -- either a plain integer, or an HTTP-date."""
    value = headers.get("retry-after")
    if not value:
        return None
    value = value.strip()
    if value.isdigit():
        return float(value)
    try:
        when = parsedate_to_datetime(value)
        return max(0.0, (when - __import__("datetime").datetime.now(when.tzinfo)).total_seconds())
    except (TypeError, ValueError):
        return None


def _classify_exception(exc: Exception) -> str:
    # Order matters: httpx.ConnectTimeout is a subclass of both TimeoutException
    # and ConnectError, so the more specific timeout check must come first.
    if isinstance(exc, httpx.ConnectTimeout):
        return "FETCH_CONNECT_TIMEOUT"
    if isinstance(exc, httpx.ReadTimeout):
        return "FETCH_READ_TIMEOUT"
    if isinstance(exc, httpx.TimeoutException):
        return "FETCH_READ_TIMEOUT"
    if isinstance(exc, httpx.TooManyRedirects):
        return "FETCH_REDIRECT_LIMIT"
    # httpx wraps ssl errors inside ConnectError; walk the cause chain rather
    # than string-matching the message.
    cause = exc
    while cause is not None:
        if type(cause).__module__ == "ssl" or type(cause).__name__ == "SSLError":
            return "FETCH_TLS_ERROR"
        cause = cause.__cause__
    if isinstance(exc, httpx.ConnectError):
        return "FETCH_CONNECTION_ERROR"
    return "FETCH_REQUEST_ERROR"


class InsuranceFetcher:
    """Bounded, host-paced GET fetcher. See module docstring.

    Three separate limits (connect / read / wall) plus a hard body-size cap;
    every failure comes back as one of FETCH_ERROR_CODES rather than a raw
    exception -- callers branch on the code, never on exception text.
    """

    def __init__(
        self,
        *,
        connect_timeout_seconds: float = 5.0,
        read_timeout_seconds: float = 15.0,
        wall_timeout_seconds: float = 60.0,
        delay_seconds: float = 2.0,
        max_body_bytes: int = 20_000_000,
        user_agent: str = "AI-Insurance-Advice-Crawler/1.0",
        client: httpx.Client | None = None,
        clock: Callable[[], float] = time.monotonic,
        sleep: Callable[[float], None] = time.sleep,
    ) -> None:
        self.connect_timeout_seconds = connect_timeout_seconds
        self.read_timeout_seconds = read_timeout_seconds
        self.wall_timeout_seconds = wall_timeout_seconds
        self.delay_seconds = delay_seconds
        self.max_body_bytes = max_body_bytes
        self.clock = clock
        self.sleep = sleep
        self._owns_client = client is None
        self.client = client or httpx.Client(
            headers={"User-Agent": user_agent}, follow_redirects=True, verify=True
        )
        self._last_request_at: dict[str, float] = {}
        self.host_delay: dict[str, float] = {}
        """Current per-host delay, starting at delay_seconds; a 429/503
        doubles it (or jumps to Retry-After if larger), each ok response
        relaxes it by 10% back down towards delay_seconds."""

    def __enter__(self) -> "InsuranceFetcher":
        return self

    def __exit__(self, *exc_info: Any) -> None:
        self.close()

    def close(self) -> None:
        if self._owns_client:
            self.client.close()

    def _delay_for(self, host: str) -> float:
        return self.host_delay.get(host, self.delay_seconds)

    def _adapt(self, host: str, status_code: int, headers: dict[str, str]) -> None:
        current = self._delay_for(host)
        if status_code in (429, 503):
            retry_after = _retry_after_seconds(headers)
            wanted = max(current * 2, 1.0, retry_after or 0.0)
            self.host_delay[host] = min(wanted, MAX_HOST_DELAY_SECONDS)
        elif status_code and status_code < 400 and current > self.delay_seconds:
            self.host_delay[host] = max(self.delay_seconds, current * 0.9)

    def _throttle(self, host: str) -> None:
        last = self._last_request_at.get(host)
        if last is not None:
            wait = self._delay_for(host) - (self.clock() - last)
            if wait > 0:
                self.sleep(wait)
        self._last_request_at[host] = self.clock()

    def get(self, url: str) -> InsuranceFetchResponse:
        host = (urlsplit(url).hostname or "").lower()
        self._throttle(host)

        start = self.clock()
        deadline = start + self.wall_timeout_seconds
        timeout = httpx.Timeout(
            connect=self.connect_timeout_seconds,
            read=self.read_timeout_seconds,
            write=self.read_timeout_seconds,
            pool=self.connect_timeout_seconds,
        )

        try:
            with self.client.stream("GET", url, timeout=timeout) as response:
                chunks: list[bytes] = []
                size = 0
                for chunk in response.iter_bytes(chunk_size=65536):
                    if self.clock() >= deadline:
                        return InsuranceFetchResponse(
                            requested_url=url,
                            final_url=str(response.url),
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            error_code="FETCH_WALL_TIMEOUT",
                            elapsed_seconds=self.clock() - start,
                        )
                    size += len(chunk)
                    if size > self.max_body_bytes:
                        return InsuranceFetchResponse(
                            requested_url=url,
                            final_url=str(response.url),
                            status_code=response.status_code,
                            headers=dict(response.headers),
                            error_code="BODY_TOO_LARGE",
                            elapsed_seconds=self.clock() - start,
                        )
                    chunks.append(chunk)
                body = b"".join(chunks)
                headers = dict(response.headers)
                status_code = response.status_code
                final_url = str(response.url)
        except httpx.HTTPError as exc:
            code = _classify_exception(exc)
            return InsuranceFetchResponse(
                requested_url=url, final_url=url, status_code=0, error_code=code, elapsed_seconds=self.clock() - start
            )

        self._adapt(host, status_code, headers)

        error_code = None
        if status_code == 429:
            error_code = "HTTP_429"
        elif 500 <= status_code < 600:
            error_code = "HTTP_5XX"

        return InsuranceFetchResponse(
            requested_url=url,
            final_url=final_url,
            status_code=status_code,
            headers=headers,
            body=body,
            error_code=error_code,
            elapsed_seconds=self.clock() - start,
        )
