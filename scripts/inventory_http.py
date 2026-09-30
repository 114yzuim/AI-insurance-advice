"""Shared HTTP helpers for the inventory audit/download scripts.

Kept in one place so audit_product_links.py, audit_policy_documents.py and
download_pdf_snapshots.py can't drift from each other on how they build
outbound request headers.
"""

from urllib.parse import urlsplit

DEFAULT_HEADERS = {
    "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
    "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
    "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
}


def referer_for_url(url: str) -> str:
    """Best-effort same-origin Referer for `url`.

    A hardcoded single-company Referer breaks other companies' anti-hotlinking
    checks; falling back to the target's own origin is the safe generic
    default when no better per-source Referer is known.
    """
    parts = urlsplit(url)
    if not parts.scheme or not parts.netloc:
        return ""
    return f"{parts.scheme}://{parts.netloc}/"
