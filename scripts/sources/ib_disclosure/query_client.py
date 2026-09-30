"""IB (保險業公開資訊觀測站) query client -- one plain ASP.NET GET+POST flow.

Verified live (2026-09-13), against
https://ins-info.ib.gov.tw/customer/Property_Layout.aspx?UID=03557115:

  - GET that URL: plain 200, no CAPTCHA, carries the usual ASP.NET WebForms
    hidden fields (__VIEWSTATE/__VIEWSTATEGENERATOR/__VIEWSTATEENCRYPTED/
    __EVENTVALIDATION).
  - POST the same URL with `ctl00$MainContent$txtProductCode=""`,
    `ctl00$MainContent$txtKeyWord=""`, `ctl00$MainContent$btnQuery="查詢"`
    (plus those hidden fields, read off the GET) -- a completely ordinary
    form submission with a blank query, i.e. "list everything" -- returns
    that company's full product list, page 1 of 192 for this company.
  - Later pages are a plain GET to `Property_Layout.aspx?Page=N&UID=...`,
    *not* a `__doPostBack` -- much simpler than expected. This was only
    confirmed to work within the same browser session that had already
    submitted the query above; this client therefore always calls query()
    before get_page(), using one persistent httpx.AsyncClient (cookies
    carried across requests, same session) rather than relying on a cold
    GET to a later page working on its own.

This is a plain, publicly-reachable HTML form -- no CAPTCHA, no login. It is
NOT the same category of thing as TII's Query.aspx (CAPTCHA-gated) or
DetailList.aspx (redirects on direct access): submitting an empty search on
a page whose own UI invites exactly that is not a bypass of anything. See
scripts/sources/ib_disclosure/README.md for the fuller reasoning and scope.

`post_event()` (verified live 2026-09-13, product 1011212290040101, function
2 -- 條款內容) is the same mechanism applied to a detail page's document
LinkButton: GET the detail page for its current hidden fields, POST back
with `__EVENTTARGET` set to the LinkButton's control name (e.g.
"ctl00$MainContent$LinkButton1"). The response is NOT the file -- it's an
HTML page containing `<script>window.open('https://ins-info.ib.gov.tw/
FSC/DownLoad.aspx?file=<opaque-token>')</script>`. That DownLoad.aspx URL
*is* the real file: confirmed via a plain GET returning
`Content-Disposition: attachment; filename="1011212290040101.PDF"`,
`Content-Type: application/octet-stream`, and a body starting with the PDF
magic bytes (`%PDF`). See download_client.py, which does exactly these two
steps (resolve the DownLoad.aspx URL, then fetch it) and nothing more --
the opaque `file=` token is used verbatim as the server generated it, never
decoded or reconstructed.
"""

from __future__ import annotations

import asyncio
import hashlib
import sys
import time
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from urllib.parse import parse_qs, urlsplit, urlunsplit

import httpx
from bs4 import BeautifulSoup

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from inventory_http import DEFAULT_HEADERS, referer_for_url  # noqa: E402

IB_HOST = "ins-info.ib.gov.tw"
REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_SNAPSHOT_DIR = REPO_ROOT / "backend" / "data" / "ib_disclosure_snapshots"

_HIDDEN_FIELDS = ("__VIEWSTATE", "__VIEWSTATEGENERATOR", "__VIEWSTATEENCRYPTED", "__EVENTVALIDATION")


def _is_ib_url(url: str) -> bool:
    parts = urlsplit(url)
    return parts.scheme == "https" and parts.hostname == IB_HOST


def extract_hidden_fields(html: str) -> dict[str, str]:
    """Read __VIEWSTATE et al. off a page so a subsequent POST can carry them.

    Every ASP.NET WebForms postback needs these -- without them the server
    rejects the postback (or resets to a stateless default), it's not
    optional plumbing to skip.
    """
    soup = BeautifulSoup(html, "html.parser")
    fields: dict[str, str] = {}
    for name in _HIDDEN_FIELDS:
        tag = soup.find("input", attrs={"name": name})
        fields[name] = tag.get("value", "") if tag else ""
    return fields


@dataclass
class FetchResult:
    url: str
    final_url: str
    status_code: int
    content: bytes
    content_type: str
    content_disposition: str  # e.g. 'attachment; filename="1011212290040101.PDF"' -- "" if absent
    snapshot_path: str  # relative to repo root
    checksum: str
    fetched_at: str


class IbQueryClient:
    """One rate-limited, cookie-persisting session against ins-info.ib.gov.tw."""

    def __init__(
        self,
        snapshot_dir: Path = DEFAULT_SNAPSHOT_DIR,
        min_interval_seconds: float = 2.0,
        timeout: float = 20.0,
        verify: bool = True,
    ) -> None:
        self.snapshot_dir = snapshot_dir
        self.snapshot_dir.mkdir(parents=True, exist_ok=True)
        self.min_interval_seconds = min_interval_seconds
        self._last_request_at = 0.0
        self._client = httpx.AsyncClient(
            timeout=timeout, follow_redirects=True, headers=dict(DEFAULT_HEADERS), verify=verify
        )

    async def __aenter__(self) -> "IbQueryClient":
        return self

    async def __aexit__(self, *exc_info) -> None:
        await self._client.aclose()

    async def _throttle(self) -> None:
        elapsed = time.monotonic() - self._last_request_at
        wait = self.min_interval_seconds - elapsed
        if wait > 0:
            await asyncio.sleep(wait)
        self._last_request_at = time.monotonic()

    def _save_snapshot(self, content: bytes, content_type: str) -> str:
        checksum = hashlib.sha256(content).hexdigest()
        ext = ".html" if "html" in content_type.lower() else ".bin"
        stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
        path = self.snapshot_dir / f"{stamp}_{checksum[:16]}{ext}"
        path.write_bytes(content)
        try:
            return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
        except ValueError:
            return str(path)

    async def _request(self, method: str, url: str, **kwargs) -> FetchResult:
        if not _is_ib_url(url):
            raise ValueError(f"refusing to fetch a non-IB URL with the IB client: {url}")
        await self._throttle()
        response = await self._client.request(method, url, headers={"Referer": referer_for_url(url)}, **kwargs)
        response.raise_for_status()
        content = response.content
        content_type = response.headers.get("content-type", "")
        return FetchResult(
            url=url,
            final_url=str(response.url),
            status_code=response.status_code,
            content=content,
            content_type=content_type,
            content_disposition=response.headers.get("content-disposition", ""),
            snapshot_path=self._save_snapshot(content, content_type),
            checksum=hashlib.sha256(content).hexdigest(),
            fetched_at=datetime.now(timezone.utc).isoformat(),
        )

    async def get(self, url: str) -> FetchResult:
        return await self._request("GET", url)

    async def query(self, query_url: str, product_code: str = "", keyword: str = "") -> FetchResult:
        """GET `query_url`, then POST the same URL with the search form
        (blank product_code/keyword by default -- "list everything", the
        same empty-query submission a human clicking "查詢" with nothing
        typed in would make).
        """
        initial = await self.get(query_url)
        html = initial.content.decode("utf-8", errors="replace")
        hidden = extract_hidden_fields(html)
        form_data = {
            **hidden,
            "ctl00$MainContent$txtProductCode": product_code,
            "ctl00$MainContent$txtKeyWord": keyword,
            "ctl00$MainContent$btnQuery": "查詢",
        }
        return await self._request("POST", query_url, data=form_data)

    async def get_page(self, query_url: str, page: int) -> FetchResult:
        """GET a later results page via the plain `?Page=N` query param.

        Only meaningful after `query()` has already run once on this same
        client instance (same cookies) -- see module/class docstring.
        """
        parts = urlsplit(query_url)
        uid = parse_qs(parts.query).get("UID", [""])[0]
        page_url = urlunsplit((parts.scheme, parts.netloc, parts.path, f"Page={page}&UID={uid}", ""))
        return await self.get(page_url)

    async def post_event(self, page_url: str, event_target: str, event_argument: str = "") -> FetchResult:
        """GET `page_url` (fresh hidden fields for THIS page), then POST it
        back with `__EVENTTARGET=event_target` -- the same thing clicking an
        ASP.NET LinkButton does. See
        scripts/sources/ib_disclosure/download_client.py for what this is
        for (resolving a document's actual download URL).
        """
        initial = await self.get(page_url)
        html = initial.content.decode("utf-8", errors="replace")
        hidden = extract_hidden_fields(html)
        form_data = {**hidden, "__EVENTTARGET": event_target, "__EVENTARGUMENT": event_argument}
        return await self._request("POST", page_url, data=form_data)
