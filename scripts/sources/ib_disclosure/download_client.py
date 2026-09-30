"""Resolve and fetch the actual file behind an IB LinkButton document.

Verified live (2026-09-13), product 1011212290040101 (臺灣產物住宅火災保險附加
地震基本保險), function 2 (條款內容):

  1. `IbQueryClient.post_event(detail_url, event_target)` -- GET the detail
     page for its current hidden fields, POST back with `__EVENTTARGET` set
     to the LinkButton's control name (e.g. "ctl00$MainContent$LinkButton1").
     The response is NOT the file. It's an HTML page whose body contains:
         <script>window.open('https://ins-info.ib.gov.tw/FSC/DownLoad.aspx?file=<opaque-token>')</script>
  2. That `DownLoad.aspx?file=...` URL *is* the real file: a plain GET on it
     returned `Content-Disposition: attachment; filename="1011212290040101.PDF"`,
     `Content-Type: application/octet-stream`, 440,956 bytes starting with
     the PDF magic bytes (`%PDF`).

This module does exactly those two steps and nothing else. The `file=`
token is used byte-for-byte as the server generated it -- never decoded,
reconstructed, or guessed at (it uses some opaque escaping of its own, e.g.
literal "!pc002f" sequences in place of what look like encoded "/"
characters; that's the server's business, not ours).

What this does NOT do: submit TII's Query.aspx, solve any CAPTCHA, or
resolve a document whose page redirected to the search entry (see
detail_parser.py's `redirected_to_search` status -- callers should skip
those rather than call this module on them).
"""

from __future__ import annotations

import hashlib
import re
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parents[2]
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
THIS_DIR = Path(__file__).resolve().parent
if str(THIS_DIR) not in sys.path:
    sys.path.insert(0, str(THIS_DIR))

from failure_classifier import extract_title_and_text  # noqa: E402

REPO_ROOT = Path(__file__).resolve().parents[3]
DEFAULT_DOCUMENT_SNAPSHOT_DIR = REPO_ROOT / "backend" / "data" / "ib_document_snapshots"

_DOWNLOAD_URL_RE = re.compile(r"window\.open\('([^']*DownLoad\.aspx[^']*)'\)")
# Verified live 2026-09-19: IB's edge WAF rejects (as "Request Rejected")
# any DownLoad.aspx URL whose opaque `file=` token happens to contain one of
# these substrings -- the token is encrypted, and for some files one fixed
# ciphertext block deterministically spells "drOp", which the WAF's SQL-
# injection signature matches (7/7 blocked tokens contain it at the same
# offset; 0/365 successfully downloaded tokens do). Sending such a URL can
# never succeed, so download_document() skips the GET entirely instead of
# earning another block. Only substrings actually proven to trigger this are
# listed; extend from evidence, never by guess (a wrong entry would skip
# a perfectly good download). This is NOT a bypass: we do not re-encode or
# alter the URL, we just decline to send a request known to be rejected.
WAF_TRIGGER_SUBSTRINGS = ("drop",)

_FILENAME_RE = re.compile(r'filename\*?=(?:UTF-8\'\')?"?([^";]+)"?', re.I)


@dataclass
class DownloadResult:
    status: str  # "downloaded" | "no_download_link" | "html_error" | "failed"
    detail_url: str
    event_target: str
    download_url: str = ""
    final_url: str = ""
    local_path: str = ""  # relative to repo root
    checksum: str = ""
    content_type: str = ""
    filename: str = ""
    file_size: int = 0
    error: str = ""
    # Populated on "no_download_link"/"html_error" only -- see
    # failure_classifier.FailureEvidence. A plain dict (not that dataclass
    # itself) so this stays trivially json.dumps-able for
    # document_registry.metadata.
    error_evidence: dict = field(default_factory=dict)


def _filename_from_content_disposition(header: str) -> str:
    match = _FILENAME_RE.search(header or "")
    return match.group(1).strip() if match else ""


def _guess_extension(filename: str, content_type: str) -> str:
    if filename and "." in filename:
        return "." + filename.rsplit(".", 1)[-1].lower()
    if "pdf" in (content_type or "").lower():
        return ".pdf"
    return ".bin"


def save_document_snapshot(content: bytes, filename: str, content_type: str, snapshot_dir: Path) -> str:
    """Content-addressed by checksum -- downloading the same file twice
    (e.g. a re-run) writes to the same path instead of duplicating it.
    """
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    checksum = hashlib.sha256(content).hexdigest()
    ext = _guess_extension(filename, content_type)
    path = snapshot_dir / f"{checksum}{ext}"
    if not path.exists():
        path.write_bytes(content)
    try:
        return str(path.relative_to(REPO_ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


async def resolve_download_url(client: Any, detail_url: str, event_target: str) -> tuple[str, Any]:
    """POST the LinkButton's event and pull the DownLoad.aspx URL out of the
    response's `window.open(...)` script. Returns ("", post_result) if the
    page didn't contain one (e.g. the button was decorative, or something
    about this product/function has no file after all).
    """
    post_result = await client.post_event(detail_url, event_target)
    html = post_result.content.decode("utf-8", errors="replace")
    match = _DOWNLOAD_URL_RE.search(html)
    return (match.group(1) if match else ""), post_result


async def download_document(
    client: Any,
    detail_url: str,
    event_target: str,
    snapshot_dir: Path = DEFAULT_DOCUMENT_SNAPSHOT_DIR,
) -> DownloadResult:
    """Full two-step resolve + fetch. Never raises on an ordinary "nothing
    to download" outcome -- those come back as a DownloadResult with a
    non-"downloaded" status; only unexpected transport errors propagate.
    """
    download_url, post_result = await resolve_download_url(client, detail_url, event_target)
    if not download_url:
        looks_like_html_error = "text/html" in (post_result.content_type or "").lower()
        is_error_page = looks_like_html_error and _looks_like_error_page(post_result.content)
        status = "html_error" if is_error_page else "no_download_link"
        # Even the "no_download_link" case (postback succeeded but produced
        # no window.open(...) at all) gets evidence recorded -- see
        # failure_classifier's inline_text category, which specifically
        # looks for stage="resolve" + no error markers to catch "this
        # LinkButton was never a file download in the first place".
        return DownloadResult(
            status=status,
            detail_url=detail_url,
            event_target=event_target,
            error_evidence=_build_evidence(post_result, stage="resolve"),
        )

    token = download_url.split("file=", 1)[-1].lower()
    trigger = next((sub for sub in WAF_TRIGGER_SUBSTRINGS if sub in token), None)
    if trigger:
        return DownloadResult(
            status="html_error",
            detail_url=detail_url,
            event_target=event_target,
            download_url=download_url,
            final_url=download_url,
            error=f"skipped GET: download token contains {trigger!r}, known to trigger IB's WAF",
            error_evidence={
                "stage": "preflight",
                "status_code": 0,
                "content_type": "",
                "content_length": 0,
                "final_url": download_url,
                "title": "",
                "text_sample": "",
                "snapshot_path": post_result.snapshot_path,
                "preflight_match": trigger,
            },
        )

    file_result = await client.get(download_url)
    content_type = file_result.content_type or ""
    if "text/html" in content_type.lower():
        return DownloadResult(
            status="html_error",
            detail_url=detail_url,
            event_target=event_target,
            download_url=download_url,
            final_url=file_result.final_url,
            error="DownLoad.aspx returned HTML instead of a file",
            error_evidence=_build_evidence(file_result, stage="fetch"),
        )

    filename = _filename_from_content_disposition(file_result.content_disposition)
    local_path = save_document_snapshot(file_result.content, filename, content_type, snapshot_dir)
    return DownloadResult(
        status="downloaded",
        detail_url=detail_url,
        event_target=event_target,
        download_url=download_url,
        final_url=file_result.final_url,
        local_path=local_path,
        checksum=file_result.checksum,
        content_type=content_type,
        filename=filename,
        file_size=len(file_result.content),
    )


def _build_evidence(fetch_result: Any, stage: str) -> dict:
    """Turn a query_client.FetchResult into the structured evidence dict
    the task asked for -- status_code, content_type, content_length,
    final_url, error page title, first 500 chars of plain text -- instead
    of just the one-line "HTML instead of a file" string this used to
    record. `fetch_result` already has its raw bytes saved to disk as an
    .html snapshot by IbQueryClient._save_snapshot (see its snapshot_path);
    this only adds the *structured* summary on top so
    scripts/analyze_ib_download_failures.py can aggregate without re-reading
    every snapshot file.
    """
    html = fetch_result.content.decode("utf-8", errors="replace")
    title, text_sample = extract_title_and_text(html)
    return {
        "stage": stage,
        "status_code": fetch_result.status_code,
        "content_type": fetch_result.content_type or "",
        "content_length": len(fetch_result.content),
        "final_url": fetch_result.final_url,
        "title": title,
        "text_sample": text_sample,
        "snapshot_path": fetch_result.snapshot_path,
    }


def _looks_like_error_page(content: bytes) -> bool:
    text = content.decode("utf-8", errors="replace")
    return any(marker in text for marker in ("發生錯誤", "Server Error", "找不到", "Object reference"))
