"""Extract attachment links from a TII product detail page.

TII serves per-product attachments (商品內容說明/保單條款/要保書/費率表/簽署人員
名冊 ...) through a direct file handler, `Open2.ashx?id=<uuid>`, rather than a
static file path. This module only looks for that pattern -- it does not
guess at other URL shapes, since we haven't verified this against more than
one live sample yet (see README in this directory).
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

from source import DocumentType, TiiDocumentLink, classify_document_label  # noqa: E402

OPEN_HANDLER_RE = re.compile(r"Open2\.ashx\?id=([0-9a-fA-F-]{8,})")

# Anchor text that names the *action* ("download this"), not the document --
# when this is all we have, the row's other cell is the real label.
_GENERIC_ANCHOR_TEXT = {"下載", "下载", "檢視", "检视", "查看", "開啟", "开启", "view", "download"}


def extract_documents(html: str, base_url: str) -> list[TiiDocumentLink]:
    """Find every Open2.ashx attachment link on a detail page.

    `base_url` is the detail page URL the HTML came from, used to resolve any
    relative href into an absolute one.
    """
    soup = BeautifulSoup(html, "html.parser")
    documents: list[TiiDocumentLink] = []
    seen_ids: set[str] = set()

    for anchor in soup.find_all("a", href=True):
        href = anchor["href"]
        match = OPEN_HANDLER_RE.search(href)
        if not match:
            continue
        open_id = match.group(1)
        if open_id in seen_ids:
            continue
        seen_ids.add(open_id)

        anchor_text = anchor.get_text(strip=True)
        row_label = _nearest_label_text(anchor)
        # The anchor's own text is often a generic "下載"/"檢視" rather than the
        # document type -- the row's other cell usually carries the real type
        # name, so prefer classifying on that and only fall back to the
        # anchor text (covers pages where the link text *is* the type, e.g.
        # "要保書.pdf").
        document_type = classify_document_label(row_label)
        if document_type is DocumentType.OTHER:
            document_type = classify_document_label(anchor_text)
        # Same reasoning for the human-facing label: a generic action word
        # like "下載" tells a reader nothing, so prefer the row's label text
        # when the anchor text itself doesn't name the document.
        if anchor_text.lower() in _GENERIC_ANCHOR_TEXT and row_label:
            label = row_label
        else:
            label = anchor_text or row_label

        documents.append(
            TiiDocumentLink(
                label=label,
                url=urljoin(base_url, href),
                open_id=open_id,
                document_type=document_type,
            )
        )

    return documents


def _nearest_label_text(anchor) -> str:
    """Fall back to the same table row's leading cell text as the label.

    Some result tables put the download link in one <td> and the document
    type name in a sibling <td> in the same <tr>, with no link text at all
    (e.g. a plain "下載" icon/link). This walks up to the row and takes the
    first non-empty cell's text as a best-effort label.
    """
    row = anchor.find_parent("tr")
    if row is None:
        return ""
    for cell in row.find_all(["td", "th"]):
        text = cell.get_text(strip=True)
        if text:
            return text
    return ""
