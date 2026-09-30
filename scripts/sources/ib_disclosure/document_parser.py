"""Extract document references from an IB product page.

Verified live (2026-09-13) against several real property5-1-N.aspx detail
pages: EVERY actual file reference on IB (policy terms PDF, rate-table XLS,
claim-procedure DOC, ...) is an ASP.NET LinkButton --
`<a href="javascript:__doPostBack('ctl00$MainContent$LinkButtonN','')">
filename.ext</a>` -- never a plain `<a href="....pdf">`. There is no static
URL sitting in the HTML to read off. Per this project's "don't fabricate a
URL" rule, `extract_linkbutton_documents()` records these with the visible
filename as `label` and the postback's event target as `source_document_id`,
but `url=""` -- it does not attempt the postback to find out what it
actually returns (a redirect? streamed bytes with no separate URL at all?
untested, out of scope for this phase). `extract_documents()` is kept for
the (so far unseen) case of a plain static link -- e.g. if IB ever changes
this, or a different page section uses one -- and only recognizes the
`property5-1-` per-document-type page pattern plus common file extensions.
"""

from __future__ import annotations

import re
import sys
from pathlib import Path
from urllib.parse import urljoin

from bs4 import BeautifulSoup

_THIS_DIR = Path(__file__).resolve().parent
if str(_THIS_DIR) not in sys.path:
    sys.path.insert(0, str(_THIS_DIR))

from source import IbDocumentLink  # noqa: E402

_DOCUMENT_HREF_HINTS = ("property5-1-", ".pdf", ".doc", ".docx", ".xls", ".xlsx")
_IGNORED_HREF_PREFIXES = ("#", "mailto:")
_POSTBACK_RE = re.compile(r"__doPostBack\(\s*'([^']+)'\s*,\s*'([^']*)'\s*\)")


def extract_documents(html: str, base_url: str) -> list[IbDocumentLink]:
    """Find plain, static `<a href="...">` document links, if any exist.

    See module docstring: every real IB document we've seen is a
    LinkButton, not one of these -- this exists for the (unconfirmed) case
    of a page that does use a static link, so it isn't silently unhandled
    if one ever turns up.
    """
    soup = BeautifulSoup(html, "html.parser")
    documents: list[IbDocumentLink] = []
    seen_urls: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        if not href or href.lower().startswith(_IGNORED_HREF_PREFIXES) or href.lower().startswith("javascript:"):
            continue
        if not any(hint in href.lower() for hint in _DOCUMENT_HREF_HINTS):
            continue

        absolute_url = urljoin(base_url, href)
        if absolute_url in seen_urls:
            continue
        seen_urls.add(absolute_url)

        label = anchor.get_text(strip=True) or _nearest_label_text(anchor)
        documents.append(IbDocumentLink(label=label, url=absolute_url))

    return documents


def extract_linkbutton_documents(html: str) -> list[IbDocumentLink]:
    """Find LinkButton-only document references (see module docstring).

    Each is recorded with url="" and source_document_id set to the
    postback's event target (e.g. "ctl00$MainContent$LinkButton1") -- real
    evidence a file exists and what it's named, without inventing a
    download URL that was never actually observed.
    """
    soup = BeautifulSoup(html, "html.parser")
    documents: list[IbDocumentLink] = []
    seen_targets: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"].strip()
        match = _POSTBACK_RE.search(href)
        if not match:
            continue
        event_target = match.group(1)
        label = anchor.get_text(strip=True)
        if not label:
            continue  # some LinkButtons on these pages are empty/decorative -- nothing to record
        if event_target in seen_targets:
            continue
        seen_targets.add(event_target)
        documents.append(IbDocumentLink(label=label, url="", source_document_id=event_target))

    return documents


def _nearest_label_text(anchor) -> str:
    """Same fallback strategy as scripts/sources/tii/document_parser.py:
    use the enclosing table row's first non-empty cell text when the anchor
    itself has no useful text (e.g. an icon-only link).
    """
    row = anchor.find_parent("tr")
    if row is None:
        return ""
    for cell in row.find_all(["td", "th"]):
        text = cell.get_text(strip=True)
        if text:
            return text
    return ""
