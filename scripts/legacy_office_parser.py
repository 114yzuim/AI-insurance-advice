"""Parse legacy binary Office formats -- .xls (real, via xlrd) and .doc
(LibreOffice headless, PRODUCTION path -- Linux/Railway-safe; an opt-in
Windows COM fallback exists too, for local testing only, never on by
default and never the production path).

Kept separate from scripts/document_parser_service.py on purpose: that
module's dispatch table only covers formats with an unconditionally-safe,
always-available parser (pdfplumber/pypdf, python-docx, openpyxl, csv).
.doc's parser needs an external binary/process either way (LibreOffice) or
COM automation (Windows desktop only) -- different enough from "just import
a pure-Python library" that keeping it in its own module makes that
distinction, and the opt-in boundary around COM, a single obvious import
rather than a comment buried inside document_parser_service.py's dispatch.

.doc parser priority (see parse_doc()):
    1. LibreOffice headless (`soffice`/`libreoffice` on PATH) -- works on
       Linux, so this IS the production path for a Railway worker (see
       Task 2's Dockerfile.worker, which installs libreoffice).
    2. Windows COM automation via a local MS Word install -- ONLY when the
       caller passes enable_windows_com=True explicitly. Never inferred
       from the environment (even when pywin32 + Word are both available),
       and LibreOffice is always tried first even when this is enabled, so
       COM only ever fires as a fallback on a machine that doesn't have
       LibreOffice -- exactly the Windows-desktop-without-LibreOffice case
       this exists for during local development.
    3. Neither available -> `parser_unavailable`, never a fabricated
       "parsed" result.

xlrd 2.x (unlike openpyxl) reads ONLY the legacy .xls BIFF format -- it
dropped .xlsx support upstream in favor of openpyxl, which is exactly the
split this project wants (openpyxl for .xlsx, xlrd for .xls, no overlap).

Usage:
    result = parse_xls(Path("...legacy.xls"))
    result.status  # "parsed" | "parse_failed" | "parser_unavailable"

    result = parse_doc(Path("...legacy.doc"))  # LibreOffice if present, else parser_unavailable
    result.status  # "parsed" | "parse_failed" | "parser_unavailable"

    result = parse_doc(Path("...legacy.doc"), enable_windows_com=True)  # + COM fallback, local only
    result.status  # "parsed" | "parse_failed" | "parser_unavailable"
"""

from __future__ import annotations

import shutil
import subprocess
import sys
import tempfile
from dataclasses import dataclass, field
from pathlib import Path

SCRIPTS_DIR = Path(__file__).resolve().parent
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

from document_parser_service import ParsedChunk, _build_chunks, _looks_like_blocked_or_error_html  # noqa: E402

PARSER_NAME_XLS = "legacy_office_parser.xlrd"
PARSER_NAME_DOC_LIBREOFFICE = "legacy_office_parser.libreoffice"
PARSER_NAME_DOC_COM = "legacy_office_parser.windows_com"
LIBREOFFICE_TIMEOUT_SECONDS = 60.0
LIBREOFFICE_BINARY_NAMES = ("soffice", "libreoffice")


@dataclass
class DocumentParseResult:
    status: str  # parsed | parser_unavailable | parse_failed
    parser_name: str
    parser_version: str = ""
    text: str = ""
    chunks: list[ParsedChunk] = field(default_factory=list)
    table_count: int = 0
    page_count: int | None = None
    warnings: list[str] = field(default_factory=list)
    errors: list[str] = field(default_factory=list)


def parse_xls(
    path: Path,
    *,
    document_type: str = "",
    source_url: str = "",
    document_id: str = "",
    chunk_size: int = 1800,
    chunk_overlap: int = 180,
) -> DocumentParseResult:
    """Legacy .xls via xlrd. Every sheet becomes a `[sheet name]` block of
    ` | `-joined non-empty cells per row -- same convention as
    document_parser_service._parse_xlsx, so .xls and .xlsx documents read
    identically downstream regardless of which one a given product happens
    to have.
    """
    try:
        import xlrd
    except ImportError:
        return DocumentParseResult(
            status="parser_unavailable",
            parser_name=PARSER_NAME_XLS,
            warnings=["xlrd is not installed"],
        )

    data = path.read_bytes()
    blocked_reason = _looks_like_blocked_or_error_html(data, ".xls")
    if blocked_reason:
        return DocumentParseResult(
            status="parse_failed",
            parser_name=PARSER_NAME_XLS,
            errors=[f"file looks like a blocked/error HTML page, not a real .xls -- {blocked_reason}"],
        )

    try:
        workbook = xlrd.open_workbook(file_contents=data)
    except Exception as exc:  # noqa: BLE001 -- xlrd raises a mix of its own and generic exceptions on malformed files
        return DocumentParseResult(status="parse_failed", parser_name=PARSER_NAME_XLS, parser_version=xlrd.__version__, errors=[f".xls parse failed: {exc}"])

    parts: list[str] = []
    table_count = 0
    for sheet in workbook.sheets():
        sheet_rows = []
        for row_index in range(sheet.nrows):
            cells = [str(cell.value).strip() for cell in sheet.row(row_index) if str(cell.value).strip()]
            if cells:
                sheet_rows.append(" | ".join(cells))
        if sheet_rows:
            table_count += 1
            parts.append(f"[{sheet.name}]\n" + "\n".join(sheet_rows))

    text = "\n\n".join(parts)
    if not text.strip():
        return DocumentParseResult(
            status="parse_failed", parser_name=PARSER_NAME_XLS, parser_version=xlrd.__version__,
            table_count=table_count, errors=["xlrd produced no text (workbook has no non-empty cells)"],
        )

    chunks = _build_chunks(
        text, document_type=document_type, source_url=source_url, document_id=document_id,
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
    )
    return DocumentParseResult(
        status="parsed", parser_name=PARSER_NAME_XLS, parser_version=xlrd.__version__,
        text=text, chunks=chunks, table_count=table_count,
    )


def _find_libreoffice_binary() -> str | None:
    for name in LIBREOFFICE_BINARY_NAMES:
        path = shutil.which(name)
        if path:
            return path
    return None


def libreoffice_available() -> bool:
    return _find_libreoffice_binary() is not None


def _parse_doc_libreoffice(path: Path) -> DocumentParseResult:
    """Convert .doc -> .txt with `soffice --headless --convert-to txt`,
    then read the result. This is the ONLY .doc path this project runs in
    production (see Dockerfile.worker) -- LibreOffice headless conversion
    works identically on Linux and Windows, unlike COM automation below.

    Each call spawns its own `soffice` process rather than reusing a long-
    lived one: LibreOffice's headless mode is known to wedge under
    concurrent/rapid reuse of one profile, and this project's parse volume
    (hundreds of documents, not thousands per second) doesn't need the
    throughput a persistent instance would buy -- one clean process per
    document is simpler and can't leak state between documents.
    """
    binary = _find_libreoffice_binary()
    if binary is None:
        return DocumentParseResult(
            status="parser_unavailable",
            parser_name=PARSER_NAME_DOC_LIBREOFFICE,
            warnings=[f"LibreOffice not found on PATH (looked for {', '.join(LIBREOFFICE_BINARY_NAMES)})"],
        )

    data = path.read_bytes()
    blocked_reason = _looks_like_blocked_or_error_html(data, ".doc")
    if blocked_reason:
        return DocumentParseResult(
            status="parse_failed",
            parser_name=PARSER_NAME_DOC_LIBREOFFICE,
            errors=[f"file looks like a blocked/error HTML page, not a real .doc -- {blocked_reason}"],
        )

    with tempfile.TemporaryDirectory(prefix="legacy_office_libreoffice_") as tmp_dir:
        # A dedicated -env:UserInstallation profile per call, inside the
        # same disposable tmp_dir, avoids two concurrent parse_document_
        # snapshots.py processes (or a retried run) colliding on
        # LibreOffice's default profile lock.
        user_profile_uri = Path(tmp_dir, "lo_profile").as_uri()
        try:
            completed = subprocess.run(
                [
                    binary,
                    "--headless",
                    "--norestore",
                    f"-env:UserInstallation={user_profile_uri}",
                    "--convert-to",
                    "txt:Text",
                    "--outdir",
                    tmp_dir,
                    str(path),
                ],
                capture_output=True,
                timeout=LIBREOFFICE_TIMEOUT_SECONDS,
                check=False,
            )
        except subprocess.TimeoutExpired:
            return DocumentParseResult(
                status="parse_failed",
                parser_name=PARSER_NAME_DOC_LIBREOFFICE,
                errors=[f"LibreOffice conversion timed out after {LIBREOFFICE_TIMEOUT_SECONDS}s"],
            )
        except OSError as exc:  # binary found by shutil.which but failed to actually launch
            return DocumentParseResult(
                status="parser_unavailable",
                parser_name=PARSER_NAME_DOC_LIBREOFFICE,
                warnings=[f"failed to launch LibreOffice: {exc}"],
            )

        output_path = Path(tmp_dir) / f"{path.stem}.txt"
        if completed.returncode != 0 or not output_path.exists():
            stderr = completed.stderr.decode("utf-8", errors="replace").strip()[:500]
            return DocumentParseResult(
                status="parse_failed",
                parser_name=PARSER_NAME_DOC_LIBREOFFICE,
                errors=[f"LibreOffice conversion failed (exit {completed.returncode}): {stderr or '(no stderr)'}"],
            )
        text = output_path.read_text(encoding="utf-8", errors="replace").strip()

    if not text:
        return DocumentParseResult(status="parse_failed", parser_name=PARSER_NAME_DOC_LIBREOFFICE, errors=["LibreOffice produced no text"])

    return DocumentParseResult(status="parsed", parser_name=PARSER_NAME_DOC_LIBREOFFICE, text=text)


def _windows_com_available() -> bool:
    try:
        import win32com.client  # noqa: F401
    except ImportError:
        return False
    return sys.platform == "win32"


def _parse_doc_windows_com(path: Path) -> DocumentParseResult:
    """Opt-in only -- see parse_doc()'s docstring and module docstring.
    Never called unless enable_windows_com=True AND LibreOffice wasn't
    available.
    """
    if not _windows_com_available():
        return DocumentParseResult(
            status="parser_unavailable",
            parser_name=PARSER_NAME_DOC_COM,
            warnings=["--enable-windows-com was set but pywin32/win32com is not available on this platform"],
        )

    data = path.read_bytes()
    blocked_reason = _looks_like_blocked_or_error_html(data, ".doc")
    if blocked_reason:
        return DocumentParseResult(
            status="parse_failed",
            parser_name=PARSER_NAME_DOC_COM,
            errors=[f"file looks like a blocked/error HTML page, not a real .doc -- {blocked_reason}"],
        )

    import win32com.client  # local import -- only reached when enable_windows_com=True and available

    word = None
    document = None
    try:
        word = win32com.client.DispatchEx("Word.Application")
        word.Visible = False
        word.DisplayAlerts = 0
        # Word's COM API only opens by an absolute path string, not bytes --
        # unlike every other parser in this project it must be handed the
        # real file on disk, not decoded in memory. This is exactly the
        # kind of environment coupling that keeps this path Windows-only.
        document = word.Documents.Open(str(path.resolve()), ReadOnly=True)
        text = document.Content.Text
    except Exception as exc:  # noqa: BLE001 -- COM errors surface as generic pywintypes.com_error
        return DocumentParseResult(status="parse_failed", parser_name=PARSER_NAME_DOC_COM, errors=[f"Word COM parse failed: {exc}"])
    finally:
        if document is not None:
            try:
                document.Close(False)
            except Exception:  # noqa: BLE001 -- best-effort cleanup, never masks the real result
                pass
        if word is not None:
            try:
                word.Quit()
            except Exception:  # noqa: BLE001
                pass

    text = (text or "").strip()
    if not text:
        return DocumentParseResult(status="parse_failed", parser_name=PARSER_NAME_DOC_COM, errors=["Word COM produced no text"])
    return DocumentParseResult(status="parsed", parser_name=PARSER_NAME_DOC_COM, text=text)


def parse_doc(
    path: Path,
    *,
    enable_windows_com: bool = False,
    document_type: str = "",
    source_url: str = "",
    document_id: str = "",
    chunk_size: int = 1800,
    chunk_overlap: int = 180,
) -> DocumentParseResult:
    """.doc parser priority: LibreOffice headless first (production path,
    Linux-safe -- see module docstring), then Windows COM ONLY if
    `enable_windows_com=True` was passed explicitly (never inferred from
    the environment, even when pywin32 + Word happen to be available), then
    `parser_unavailable`. Never a fabricated "parsed" result.
    """
    result = _parse_doc_libreoffice(path)
    if result.status == "parser_unavailable" and enable_windows_com:
        result = _parse_doc_windows_com(path)
    elif result.status == "parser_unavailable" and not enable_windows_com:
        result.warnings = result.warnings + [
            "LibreOffice unavailable and --enable-windows-com not set -- pass --enable-windows-com "
            "for local-only testing via a real MS Word install, or install LibreOffice for production"
        ]

    if result.status != "parsed" or not result.text.strip():
        return result

    chunks = _build_chunks(
        result.text, document_type=document_type, source_url=source_url, document_id=document_id,
        chunk_size=chunk_size, chunk_overlap=chunk_overlap,
    )
    result.chunks = chunks
    return result
