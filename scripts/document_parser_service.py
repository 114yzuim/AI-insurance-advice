"""Lightweight, multi-format document parsing for this project's RAG
pipeline -- PDF (existing behavior, untouched), DOCX/XLSX/CSV (new, only
using dependencies already present in this environment), DOC/XLS (left
`downloaded_not_parsed`, same policy as before -- see module docstring's
"what's deliberately not carried over").

Concept borrowed from two places:
  - `DoclingParser` in
    C:/Users/rabbi/OneDrive/桌面/final/repo-manager/core/docling_parser.py
    (remote YZU1507A/test-yzuqa-manager) -- the ParseResult shape (status/
    parser/page_count/table_count/chunks/warnings/errors) and the
    page-count-based size guard before attempting a full parse.
  - `attachment_text.py` in
    C:/Users/rabbi/OneDrive/桌面/crawler-v1/src/crawler_v1/fetch/attachment_text.py
    (remote YZU1507A/universal-crawler) -- the general principle of one
    per-extension dispatch table with a bounded-effort extractor per type,
    and never handing a blocked/error page to a downstream indexer.

What's deliberately NOT carried over:
  - `DoclingParser` itself (repo-manager's parser class). CORRECTION worth
    being explicit about: `docling>=2.43.0` IS already a real dependency of
    this project (see backend/requirements.txt -- verified live 2026-09-14,
    `import docling` succeeds; presumably used by the OCR/policy-extraction
    pipeline, not this crawler). So "docling isn't installed" is NOT the
    reason this module doesn't call it. The actual reasons: (1) docling's
    own parser (see repo-manager/core/docling_parser.py) only accepts
    .pdf/.docx -- it has no .xlsx/.csv support at all, so this module would
    still need separate handling for those regardless; (2) this project's
    PDF path already has a proven pdfplumber/pypdf pipeline (149/149
    successful in the previous phase's live run) -- routing PDFs through
    docling's much heavier DocumentConverter (transformer-based layout
    models) instead would be an unrelated, riskier swap this phase wasn't
    asked to make; (3) for the genuinely new formats here (DOCX/XLSX/CSV),
    plain python-docx/openpyxl/csv already do the job with less machinery
    to load per parse. Revisiting PDF parsing quality (e.g. table
    structure) is a reasonable candidate for a LATER phase that explicitly
    evaluates docling against the current pipeline -- not assumed here.
  - `EasyOCR`/`RapidOCR` (docling's OCR backends). No scanned-PDF OCR need
    has come up yet in THIS module (scanned_pdf documents are already a
    distinct, tracked text_status -- see parse_pdf_snapshots.py); whatever
    OCR docling is already used for elsewhere in this project is untouched.
  - LibreOffice-based DOC/XLS conversion. Not installed in this
    environment and not something to newly depend on per the task's own
    "不要新增重依賴" constraint -- DOC/XLS stay `downloaded_not_parsed`
    until/unless that changes.
  - True OS-level parse timeouts (repo-new_crawler's child-process
    isolation via a killable subprocess). Windows has no SIGALRM, and this
    project runs on Windows locally -- a real per-parse wall-clock kill
    needs a subprocess or thread-based watchdog this phase doesn't add.
    Bounded by max_pages/max_bytes instead (checked BEFORE parsing starts,
    not interrupting a parse mid-flight) -- a cruder but cross-platform-safe
    guard against the pathological case (a 5000-page PDF) this exists for.

Usage:
    result = parse_document(
        Path("backend/data/ib_document_snapshots/<checksum>.pdf"),
        document_type="POLICY_TERMS",
        source_url="urn:ib-linkbutton:...",
        document_id="123",
    )
    result.status  # "parsed" | "downloaded_not_parsed" | "parser_unavailable" | "parse_failed" | "unsupported_type"
"""

from __future__ import annotations

import csv
import io
import sys
from dataclasses import dataclass, field
from pathlib import Path
from typing import Any

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from parse_pdf_snapshots import chunk_text, extract_pdf_text, extract_pdf_text_pypdf  # noqa: E402
from source_response_classifier import classify_source_response  # noqa: E402

PARSER_NAME = "document_parser_service"
PARSER_VERSION = "1.0"

DEFAULT_MAX_PAGES = 200
DEFAULT_MAX_BYTES = 20_000_000
DEFAULT_CHUNK_SIZE = 1800
DEFAULT_CHUNK_OVERLAP = 180

# .doc/.xls (legacy binary Office formats) have no lightweight pure-Python
# reader already in this project's dependencies (xlrd is NOT installed --
# verified live 2026-09-14; see module docstring). They're recorded as
# downloaded_not_parsed, same terminal state
# scripts/sync_document_registry_to_policy_documents.py already assigns
# them at sync time -- this function just explains why, rather than
# silently failing.
_LEGACY_OFFICE_EXTENSIONS = {".doc", ".xls"}
_SUPPORTED_EXTENSIONS = {".pdf", ".docx", ".xlsx", ".csv"}


@dataclass
class ParsedChunk:
    text: str
    chunk_index: int
    page: int | None = None
    section: str | None = None
    citation: dict[str, Any] = field(default_factory=dict)


@dataclass
class DocumentParseResult:
    status: str  # parsed | downloaded_not_parsed | parser_unavailable | parse_failed | unsupported_type
    parser_name: str
    parser_version: str = ""
    text: str = ""
    chunks: list[ParsedChunk] = field(default_factory=list)
    table_count: int = 0
    page_count: int | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


_PAGE_MARKER_RE_PREFIX = "[第 "


def _page_from_chunk_text(text: str) -> int | None:
    """extract_pdf_text() (parse_pdf_snapshots.py, unchanged) embeds "[第 N
    頁]" markers as literal text at the start of each page's contribution --
    if a chunk happens to start with one (common for the first chunk of a
    page-sized document), surface it as citation metadata instead of
    discarding it.
    """
    if not text.startswith(_PAGE_MARKER_RE_PREFIX):
        return None
    try:
        rest = text[len(_PAGE_MARKER_RE_PREFIX) :]
        number = rest.split(" ", 1)[0]
        return int(number)
    except (ValueError, IndexError):
        return None


def _build_chunks(
    text: str,
    *,
    document_type: str,
    source_url: str,
    document_id: str,
    chunk_size: int,
    chunk_overlap: int,
) -> list[ParsedChunk]:
    raw_chunks = chunk_text(text, chunk_size, chunk_overlap)
    chunks = []
    for index, chunk in enumerate(raw_chunks):
        chunks.append(
            ParsedChunk(
                text=chunk,
                chunk_index=index,
                page=_page_from_chunk_text(chunk),
                section=None,
                citation={
                    "source_url": source_url,
                    "document_id": document_id,
                    "document_type": document_type,
                },
            )
        )
    return chunks


def _looks_like_blocked_or_error_html(data: bytes, expect_extension: str) -> str | None:
    """Guard against a "PDF"/"DOCX"/... on disk that's actually a saved
    HTML error/blocked/CAPTCHA page (e.g. a DownLoad.aspx html_error -- see
    scripts/sources/ib_disclosure/download_client.py -- that slipped past
    upstream checks and got saved with the expected extension anyway).
    Returns a human-readable reason if so, None if the bytes look like the
    real thing.
    """
    sniff = data[:2048].lstrip()
    looks_like_html = sniff[:1] in (b"<", b"\xef") and (b"<html" in sniff.lower() or b"<!doctype" in sniff.lower())
    if not looks_like_html:
        return None
    text_preview = data[:4000].decode("utf-8", errors="replace")
    classification = classify_source_response(
        status_code=200, content_type="text/html", text_preview=text_preview, expected_binary=True
    )
    if classification.category == "ok":
        return None  # genuinely HTML but nothing flagged it as blocked/error -- let the caller's own type check reject it
    return f"{classification.category}: {classification.reasoning}"


def _parse_pdf(data: bytes, path: Path, max_pages: int) -> tuple[str, int | None, list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    page_count = None
    try:
        import pypdf

        page_count = len(pypdf.PdfReader(io.BytesIO(data)).pages)
    except Exception:  # noqa: BLE001 -- page count is advisory, never fatal
        pass
    if page_count and page_count > max_pages:
        errors.append(f"PDF too large: {page_count} pages exceeds max_pages={max_pages}")
        return "", page_count, warnings, errors

    try:
        text = extract_pdf_text(path, max_pages)
        if not text.strip():
            raise ValueError("pdfplumber produced no text")
    except Exception:  # noqa: BLE001 -- fall back to pypdf, same policy as parse_pdf_snapshots.py's "auto" engine
        try:
            text = extract_pdf_text_pypdf(path, max_pages)
        except Exception as exc:  # noqa: BLE001
            errors.append(f"PDF parse failed: {exc}")
            return "", page_count, warnings, errors
    return text, page_count, warnings, errors


def _parse_docx(data: bytes) -> tuple[str, int, list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        import docx
    except ImportError:
        errors.append("python-docx is not installed")
        return "", 0, warnings, errors

    try:
        document = docx.Document(io.BytesIO(data))
        parts = [paragraph.text for paragraph in document.paragraphs if paragraph.text.strip()]
        table_count = len(document.tables)
        for table in document.tables:
            for row in table.rows:
                cells = [cell.text.strip() for cell in row.cells if cell.text.strip()]
                if cells:
                    parts.append(" | ".join(cells))
        return "\n".join(parts), table_count, warnings, errors
    except Exception as exc:  # noqa: BLE001
        errors.append(f"DOCX parse failed: {exc}")
        return "", 0, warnings, errors


def _parse_xlsx(data: bytes) -> tuple[str, int, list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        import openpyxl
    except ImportError:
        errors.append("openpyxl is not installed")
        return "", 0, warnings, errors

    try:
        workbook = openpyxl.load_workbook(io.BytesIO(data), read_only=True, data_only=True)
        parts = []
        table_count = 0
        for sheet in workbook.worksheets:
            sheet_rows = []
            for row in sheet.iter_rows(values_only=True):
                cells = [str(value).strip() for value in row if value is not None and str(value).strip()]
                if cells:
                    sheet_rows.append(" | ".join(cells))
            if sheet_rows:
                table_count += 1
                parts.append(f"[{sheet.title}]\n" + "\n".join(sheet_rows))
        return "\n\n".join(parts), table_count, warnings, errors
    except Exception as exc:  # noqa: BLE001
        errors.append(f"XLSX parse failed: {exc}")
        return "", 0, warnings, errors


def _parse_csv(data: bytes) -> tuple[str, int, list[str], list[str]]:
    warnings: list[str] = []
    errors: list[str] = []
    try:
        text = data.decode("utf-8-sig")
    except UnicodeDecodeError:
        try:
            text = data.decode("big5")
        except UnicodeDecodeError:
            text = data.decode("utf-8", errors="replace")
    try:
        rows = list(csv.reader(io.StringIO(text)))
        lines = [" | ".join(cell.strip() for cell in row if cell.strip()) for row in rows]
        lines = [line for line in lines if line]
        return "\n".join(lines), (1 if rows else 0), warnings, errors
    except csv.Error as exc:
        errors.append(f"CSV parse failed: {exc}")
        return "", 0, warnings, errors


def parse_document(
    path: Path,
    *,
    document_type: str = "",
    source_url: str = "",
    document_id: str = "",
    max_pages: int = DEFAULT_MAX_PAGES,
    max_bytes: int = DEFAULT_MAX_BYTES,
    chunk_size: int = DEFAULT_CHUNK_SIZE,
    chunk_overlap: int = DEFAULT_CHUNK_OVERLAP,
) -> DocumentParseResult:
    suffix = path.suffix.lower()

    if suffix in _LEGACY_OFFICE_EXTENSIONS:
        return DocumentParseResult(
            status="downloaded_not_parsed",
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            warnings=[f"{suffix} has no lightweight parser available in this environment (see module docstring)"],
        )
    if suffix not in _SUPPORTED_EXTENSIONS:
        return DocumentParseResult(
            status="unsupported_type",
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            errors=[f"unsupported extension: {suffix}"],
        )

    try:
        size = path.stat().st_size
    except OSError as exc:
        return DocumentParseResult(status="parse_failed", parser_name=PARSER_NAME, parser_version=PARSER_VERSION, errors=[str(exc)])
    if size > max_bytes:
        return DocumentParseResult(
            status="parse_failed",
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            errors=[f"file too large: {size} bytes exceeds max_bytes={max_bytes}"],
        )

    data = path.read_bytes()

    blocked_reason = _looks_like_blocked_or_error_html(data, suffix)
    if blocked_reason:
        return DocumentParseResult(
            status="parse_failed",
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            errors=[f"file looks like a blocked/error HTML page, not a real {suffix} -- {blocked_reason}"],
        )

    page_count: int | None = None
    table_count = 0
    if suffix == ".pdf":
        text, page_count, warnings, errors = _parse_pdf(data, path, max_pages)
    elif suffix == ".docx":
        text, table_count, warnings, errors = _parse_docx(data)
    elif suffix == ".xlsx":
        text, table_count, warnings, errors = _parse_xlsx(data)
    elif suffix == ".csv":
        text, table_count, warnings, errors = _parse_csv(data)
    else:  # pragma: no cover - guarded by _SUPPORTED_EXTENSIONS above
        text, warnings, errors = "", [], [f"unsupported extension: {suffix}"]

    if errors:
        status = "parser_unavailable" if any("not installed" in e for e in errors) else "parse_failed"
        return DocumentParseResult(
            status=status,
            parser_name=PARSER_NAME,
            parser_version=PARSER_VERSION,
            page_count=page_count,
            table_count=table_count,
            warnings=warnings,
            errors=errors,
        )

    chunks = _build_chunks(
        text,
        document_type=document_type,
        source_url=source_url,
        document_id=document_id,
        chunk_size=chunk_size,
        chunk_overlap=chunk_overlap,
    )
    return DocumentParseResult(
        status="parsed" if text.strip() else "parse_failed",
        parser_name=PARSER_NAME,
        parser_version=PARSER_VERSION,
        text=text,
        chunks=chunks,
        table_count=table_count,
        page_count=page_count,
        warnings=warnings,
        errors=[] if text.strip() else ["parser produced no text"],
    )
