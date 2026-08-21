import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import pdfplumber
from pypdf import PdfReader
from inventory_db import get_inventory_connection, row_to_dict

DEFAULT_REPORT = BACKEND / "data" / "pdf_parse_report.json"


def fetch_documents(limit: int, company: str | None, retry_failed: bool) -> list[dict[str, Any]]:
    where = ["d.local_path != ''", "d.local_path IS NOT NULL"]
    params: list[Any] = []
    if retry_failed:
        where.append("d.text_status IN ('pending', 'parse_failed', 'scanned_pdf')")
    else:
        where.append("d.text_status = 'pending'")
    if company:
        where.append("p.company_name = ?")
        params.append(company)
    sql = f"""
        SELECT
            d.id AS document_id,
            d.product_db_id,
            d.local_path,
            d.checksum,
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


def get_cached_parse(checksum: str, current_document_id: int) -> str | None:
    if not checksum:
        return None
    with get_inventory_connection() as conn:
        row = conn.execute(
            """
            SELECT parsed_text
            FROM policy_documents
            WHERE checksum = ?
              AND id != ?
              AND text_status = 'parsed'
              AND parsed_text != ''
            LIMIT 1
            """,
            (checksum, current_document_id),
        ).fetchone()
    return row["parsed_text"] if row else None


def extract_pdf_text(path: Path, max_pages: int | None) -> str:
    pages: list[str] = []
    with pdfplumber.open(path) as pdf:
        iterable = pdf.pages if max_pages is None else pdf.pages[:max_pages]
        for index, page in enumerate(iterable, 1):
            text = page.extract_text(x_tolerance=1, y_tolerance=3) or ""
            text = text.strip()
            if text:
                pages.append(f"[第 {index} 頁]\n{text}")
    return "\n\n".join(pages).strip()


def extract_pdf_text_pypdf(path: Path, max_pages: int | None) -> str:
    pages: list[str] = []
    reader = PdfReader(str(path))
    iterable = reader.pages if max_pages is None else reader.pages[:max_pages]
    for index, page in enumerate(iterable, 1):
        text = page.extract_text() or ""
        text = text.strip()
        if text:
            pages.append(f"[page {index}]\n{text}")
    return "\n\n".join(pages).strip()


def chunk_text(text: str, size: int, overlap: int) -> list[str]:
    normalized = "\n".join(line.rstrip() for line in text.splitlines())
    chunks: list[str] = []
    start = 0
    while start < len(normalized):
        end = min(start + size, len(normalized))
        if end < len(normalized):
            split_at = normalized.rfind("\n", start, end)
            if split_at > start + int(size * 0.55):
                end = split_at
        chunk = normalized[start:end].strip()
        if chunk:
            chunks.append(chunk)
        if end >= len(normalized):
            break
        start = max(0, end - overlap)
    return chunks


def save_parse(document: dict[str, Any], text: str, chunks: list[str], status: str) -> None:
    with get_inventory_connection() as conn:
        conn.execute(
            """
            UPDATE policy_documents
            SET parsed_text = ?, text_status = ?, updated_at = datetime('now')
            WHERE id = ?
            """,
            (text, status, document["document_id"]),
        )
        conn.execute("DELETE FROM policy_document_chunks WHERE document_id = ?", (document["document_id"],))
        if status == "parsed":
            for index, chunk in enumerate(chunks):
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
                        index,
                        chunk,
                        max(1, len(chunk) // 3),
                    ),
                )


def parse_one(document: dict[str, Any], args: argparse.Namespace) -> dict[str, Any]:
    local_path = ROOT / document["local_path"]
    try:
        text = get_cached_parse(document.get("checksum") or "", document["document_id"])
        source = "checksum_cache" if text else "pdf"
        if text is None:
            if args.engine == "pypdf":
                text = extract_pdf_text_pypdf(local_path, args.max_pages)
            elif args.engine == "pdfplumber":
                text = extract_pdf_text(local_path, args.max_pages)
            else:
                try:
                    text = extract_pdf_text(local_path, args.max_pages)
                except Exception:
                    text = extract_pdf_text_pypdf(local_path, args.max_pages)
        if len(text.strip()) < args.min_chars:
            save_parse(document, text, [], "scanned_pdf")
            return {**document, "status": "scanned_pdf", "chars": len(text), "chunks": 0, "source": source, "error": ""}
        chunks = chunk_text(text, args.chunk_size, args.chunk_overlap)
        save_parse(document, text, chunks, "parsed")
        return {**document, "status": "parsed", "chars": len(text), "chunks": len(chunks), "source": source, "error": ""}
    except Exception as exc:
        with get_inventory_connection() as conn:
            conn.execute(
                "UPDATE policy_documents SET text_status = 'parse_failed', updated_at = datetime('now') WHERE id = ?",
                (document["document_id"],),
            )
        return {**document, "status": "parse_failed", "chars": 0, "chunks": 0, "source": "pdf", "error": str(exc)[:240]}


def main() -> None:
    parser = argparse.ArgumentParser(description="Parse downloaded PDF snapshots into text and chunks.")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--company")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--max-pages", type=int)
    parser.add_argument("--min-chars", type=int, default=80)
    parser.add_argument("--chunk-size", type=int, default=1800)
    parser.add_argument("--chunk-overlap", type=int, default=180)
    parser.add_argument("--engine", choices=["auto", "pdfplumber", "pypdf"], default="auto")
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()

    documents = fetch_documents(args.limit, args.company, args.retry_failed)
    results = [parse_one(document, args) for document in documents]
    summary: dict[str, int] = {}
    for result in results:
        summary[result["status"]] = summary.get(result["status"], 0) + 1
    payload = {
        "parsed_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "summary": summary,
        "items": results,
    }
    args.report.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.report), "total": len(results), "summary": summary}, ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
