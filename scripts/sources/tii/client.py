"""TII (保發中心) HTTP fetch client -- snapshot-only, human-in-the-loop discovery.

This client deliberately does NOT:
  - submit the site's query/search forms (Query.aspx et al. are gated by an
    image CAPTCHA on every request, including a bare company/type filter)
  - solve or relay that CAPTCHA
  - enumerate productId values to reconstruct a catalog

It only fetches URLs it is given: a product detail page, or one of its
`Open2.ashx?id=<uuid>` attachment links -- URLs a human obtained by solving
the CAPTCHA themselves, in their own browser. If TII ties attachment access
to that browser's session, pass the session cookie through `cookie_header`
(copied from browser devtools) so the fetch replays it as that same,
already-authorized session -- this is not a bypass, it's re-sending a request
the human's own browser was already allowed to make, not discovering
anything the human didn't already see.

Every fetch is cached to disk as a timestamped raw snapshot before any
parsing happens, so a parser bug never requires re-fetching from TII.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import urlsplit

import httpx

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from inventory_http import DEFAULT_HEADERS, referer_for_url  # noqa: E402

TII_ORIGIN = "https://insprod.tii.org.tw"
TII_HOST = "insprod.tii.org.tw"


def _is_tii_url(url: str) -> bool:
    """Host-exact check -- a plain str.startswith(TII_ORIGIN) would also let
    through e.g. "https://insprod.tii.org.tw.evil.example/..." since that
    string literally starts with the same prefix. Parse it and compare the
    scheme and hostname instead.
    """
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname == TII_HOST


REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "backend" / "data" / "tii_snapshots"


@dataclass
class FetchResult:
    url: str  # the URL that was requested
    final_url: str  # the URL actually served, after following redirects
    status_code: int
    content: bytes
    content_type: str
    snapshot_path: str  # relative to repo root
    checksum: str
    fetched_at: str


class TiiClient:
    """Fetches specific, human-supplied TII URLs at a fixed, gentle rate."""

    def __init__(
        self,
        cookie_header: str | None = None,
        snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
        min_interval_seconds: float = 2.0,
        timeout: float = 20.0,
        verify: bool = True,
    ) -> None:
        self.snapshot_dir = snapshot_dir
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0
        headers = dict(DEFAULT_HEADERS)
        if cookie_header:
            headers["Cookie"] = cookie_header
        self._client = httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers, verify=verify)

    async def __aenter__(self) -> "TiiClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self.min_interval_seconds - elapsed
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_at = time.monotonic()

    async def fetch(self, url: str, *, referer: str | None = None) -> FetchResult:
        """Fetch one already-known TII URL.

        `url` must be a URL a human already navigated to and saw with their
        own eyes (a search-result product, or one of its attachment links) --
        this method does not discover it for you, and refuses non-TII URLs.
        """
        if not _is_tii_url(url):
            raise ValueError(f"refusing to fetch a non-TII URL with the TII client: {url}")
        await self._throttle()
        response = await self._client.get(url, headers={"Referer": referer or referer_for_url(url)})
        response.raise_for_status()
        content = response.content
        content_type = response.headers.get("content-type", "")
        snapshot_path = self._save_snapshot(content, content_type)
        return FetchResult(
            url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            content=content,
            content_type=content_type,
            snapshot_path=snapshot_path,
            checksum=hashlib.sha256(content).hexdigest(),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    def _save_snapshot(self, content: bytes, content_type: str) -> str:
        checksum = hashlib.sha256(content).hexdigest()
        if "pdf" in content_type.lower():
            ext = ".pdf"
        elif "html" in content_type.lower():
            ext = ".html"
        else:
            ext = ".bin"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.snapshot_dir / f"{stamp}_{checksum[:16]}{ext}"
        path.write_bytes(content)
        try:
            return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            # snapshot_dir was pointed outside the repo (e.g. a scratch/test
            # directory) -- an absolute path is still a valid, usable
            # provenance record, just not a repo-relative one.
            return str(path)


async def fetch_many(urls: list[str], client: TiiClient) -> list[FetchResult]:
    """Sequential on purpose: this is one rate-limited session, not a pool."""
    results: list[FetchResult] = []
    for url in urls:
        results.append(await client.fetch(url))
    return results
