"""Parse downloaded document snapshots into text + chunks -- PDF, DOCX,
XLSX, CSV (see scripts/document_parser_service.py) and now .xls (via
scripts/legacy_office_parser.py's xlrd path) and, opt-in only, .doc (via
that same module's Windows-COM path). New CLI, deliberately NOT a
replacement for scripts/parse_pdf_snapshots.py (that script keeps working
exactly as it did -- nothing here changes its behavior or is imported by
it), so a low-risk addition rather than a rewrite.

Picks up documents scripts/sync_document_registry_to_policy_documents.py
left as text_status IN ('pending', 'downloaded_not_parsed') whose
local_path extension one of the two modules above supports. A PDF already
sitting at 'pending' is picked up here too (this script is a superset of
parse_pdf_snapshots.py's candidates for the four document_parser_service.py
extensions), and re-parsing something already 'parsed' is NOT attempted
(that text_status is left alone -- consistent with parse_pdf_snapshots.py's
own idempotency contract).

text_status vocabulary this script writes (see
scripts/policy_data_contract.py's own text_status docstring for the full
list this project uses): 'parsed', 'parse_failed', 'parser_unavailable'
(the parser this format needs isn't installed/enabled -- e.g. .doc without
--enable-windows-com), 'unsupported_legacy_format' (a legacy Office-family
extension neither document_parser_service.py nor legacy_office_parser.py
has any parser path for at all, e.g. .ppt/.rtf/.odt -- distinct from
'parser_unavailable', which means "a parser exists but isn't enabled/
installed here"). Never silently leaves something at 'downloaded_not_parsed'
forever once this script has actually looked at it -- that status is now
reserved for "hasn't been attempted by ANY parser yet".

.doc's Windows-COM path is NEVER used unless --enable-windows-com is passed
explicitly -- see legacy_office_parser.py's module docstring for why it
can't be a default (needs a real local MS Word install, Windows-only, not
appropriate for a server deploy).

Usage:
    python scripts/parse_document_snapshots.py --source ib_disclosure --limit 100
    python scripts/parse_document_snapshots.py --source ib_disclosure --limit 20 --dry-run
    python scripts/parse_document_snapshots.py --source ib_disclosure --document-extension .xls --limit 20
    python scripts/parse_document_snapshots.py --source ib_disclosure --document-extension .doc --enable-windows-com --limit 20
"""

from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))

from inventory_db import get_inventory_connection, row_to_dict  # noqa: E402
from document_parser_service import parse_document  # noqa: E402
from legacy_office_parser import parse_doc, parse_xls  # noqa: E402

DEFAULT_REPORT = BACKEND / "data" / "document_parse_report.json"

# Extensions document_parser_service.py's parse_document() dispatches
# itself (unchanged from this CLI's first version).
_DOCUMENT_PARSER_SERVICE_SUFFIXES = (".pdf", ".docx", ".xlsx", ".csv")
# Extensions this CLI routes to legacy_office_parser.py instead.
_LEGACY_OFFICE_SUFFIXES = (".xls", ".doc")
# Other legacy Office-family extensions this project has SEEN referenced in
# IB/TII document labels but has no parser path for at all, on either
# module -- reported distinctly as 'unsupported_legacy_format' rather than
# silently falling into the same bucket as "not attempted yet".
_UNSUPPORTED_LEGACY_SUFFIXES = (".ppt", ".pptx", ".rtf", ".odt", ".ods")

_ALL_HANDLED_SUFFIXES = _DOCUMENT_PARSER_SERVICE_SUFFIXES + _LEGACY_OFFICE_SUFFIXES + _UNSUPPORTED_LEGACY_SUFFIXES


def fetch_documents(
    limit: int, source: str | None, company: str | None, document_extension: str | None
) -> list[dict[str, Any]]:
    suffixes = (document_extension.lower(),) if document_extension else _ALL_HANDLED_SUFFIXES
    where = [
        "d.local_path != ''",
        "d.local_path IS NOT NULL",
        "d.text_status IN ('pending', 'downloaded_not_parsed')",
        "(" + " OR ".join("LOWER(d.local_path) LIKE ?" for _ in suffixes) + ")",
    ]
    params: list[Any] = [f"%{suffix}" for suffix in suffixes]
    if source:
        where.append("p.source = ?")
        params.append(source)
    if company:
        where.append("p.company_name = ?")
        params.append(company)
    sql = f"""
        SELECT
            d.id AS document_id,
            d.product_db_id,
            d.local_path,
            d.checksum,
            d.pdf_url,
            d.document_type,
            p.product_id,
            p.company_name,
            p.product_name
        FROM policy_documents d
        JOIN insurance_products p ON p.id = d.product_db_id
        WHERE {' AND '.join(where)}
        ORDER BY p.company_name, p.product_id, d.id
        LIMIT ?
    """
    params.append(limit)
    with get_inventory_connection() as conn:
        return [row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


def save_parse(document: dict[str, Any], result) -> None:
    with get_inventory_connection() as conn:
        conn.execute(
            "UPDATE policy_documents SET parsed_text = ?, text_status = ?, updated_at = datetime('now') WHERE id = ?",
            (result.text, result.status, document["document_id"]),
        )
        # Chunks are only ever meaningful for a 'parsed' result -- clearing
        # them on every write (not just when status == 'parsed') keeps a
        # retry that flips 'parsed' -> 'parse_failed' (e.g. a source file
        # that got corrupted between runs) from leaving stale chunks behind
        # pointing at text that's no longer this document's current state.
        conn.execute("DELETE FROM policy_document_chunks WHERE document_id = ?", (document["document_id"],))
        if result.status == "parsed":
            for chunk in result.chunks:
                conn.execute(
                    """
                    INSERT INTO policy_document_chunks (
                        document_id, product_db_id, chunk_index, text, token_estimate
                    )
                    VALUES (?, ?, ?, ?, ?)
                    """,
                    (
                        document["document_id"],
                        document["product_db_id"],
                        chunk.chunk_index,
                        chunk.text,
                        max(1, len(chunk.text) // 3),
                    ),
                )


def parse_one(document: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    local_path = ROOT / document["local_path"]
    suffix = local_path.suffix.lower()

    if suffix in _DOCUMENT_PARSER_SERVICE_SUFFIXES:
        result = parse_document(
            local_path,
            document_type=document.get("document_type") or "",
            source_url=document.get("pdf_url") or "",
            document_id=str(document["document_id"]),
            max_pages=args.max_pages,
            max_bytes=args.max_bytes,
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    elif suffix == ".xls":
        result = parse_xls(
            local_path,
            document_type=document.get("document_type") or "",
            source_url=document.get("pdf_url") or "",
            document_id=str(document["document_id"]),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    elif suffix == ".doc":
        result = parse_doc(
            local_path,
            enable_windows_com=args.enable_windows_com,
            document_type=document.get("document_type") or "",
            source_url=document.get("pdf_url") or "",
            document_id=str(document["document_id"]),
            chunk_size=args.chunk_size,
            chunk_overlap=args.chunk_overlap,
        )
    elif suffix in _UNSUPPORTED_LEGACY_SUFFIXES:
        from document_parser_service import DocumentParseResult

        result = DocumentParseResult(
            status="unsupported_legacy_format",
            parser_name="parse_document_snapshots",
            errors=[f"{suffix} is a recognized legacy Office format with no parser path in this project yet"],
        )
    else:  # pragma: no cover - fetch_documents() only ever selects _ALL_HANDLED_SUFFIXES
        from document_parser_service import DocumentParseResult

        result = DocumentParseResult(status="unsupported_type", parser_name="parse_document_snapshots", errors=[f"unhandled extension: {suffix}"])

    if not args.dry_run:
        save_parse(document, result)
    return {
        **document,
        "status": result.status,
        "chars": len(result.text),
        "chunks": len(result.chunks),
        "table_count": result.table_count,
        "page_count": result.page_count,
        "parser_name": result.parser_name,
        "warnings": result.warnings,
        "errors": result.errors,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=200)
    parser.add_argument("--source", help="Only parse documents whose insurance_products.source matches (e.g. ib_disclosure).")
    parser.add_argument("--company")
    parser.add_argument("--document-extension", help="Only parse documents with this local_path extension, e.g. .xls")
    parser.add_argument("--max-pages", type=int, default=200)
    parser.add_argument("--max-bytes", type=int, default=20_000_000)
    parser.add_argument("--chunk-size", type=int, default=1800)
    parser.add_argument("--chunk-overlap", type=int, default=180)
    parser.add_argument(
        "--enable-windows-com",
        action="store_true",
        help=".doc only: opt in to parsing via a local MS Word install through pywin32/COM automation "
        "(Windows + real Word required; never used unless this flag is passed -- see "
        "legacy_office_parser.py's module docstring).",
    )
    parser.add_argument("--dry-run", action="store_true", help="Parse and report, but write nothing to the database.")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    documents = fetch_documents(args.limit, args.source, args.company, args.document_extension)
    results = [parse_one(document, args) for document in documents]
    summary: dict[str, int] = {}
    for result in results:
        summary[result["status"]] = summary.get(result["status"], 0) + 1
    payload = {
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "total": len(results),
        "summary": summary,
        "items": results,
    }
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.report), "total": len(results), "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
