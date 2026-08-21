import argparse
import asyncio
import hashlib
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx
from inventory_db import get_inventory_connection, row_to_dict

DEFAULT_OUTPUT_ROOT = BACKEND / "data" / "documents"
DEFAULT_REPORT = BACKEND / "data" / "pdf_snapshot_downloads.json"


def safe_segment(value: str) -> str:
    value = value.strip().replace("/", "_").replace("\\", "_")
    value = re.sub(r"[<>:\"|?*\x00-\x1f]", "_", value)
    value = re.sub(r"\s+", "_", value)
    return value[:80] or "unknown"


def fetch_documents(
    limit: int,
    company: str | None,
    include_redirected: bool,
    retry_failed: bool,
    include_suspicious: bool,
) -> list[dict[str, Any]]:
    statuses = ["ok"]
    if include_redirected:
        statuses.append("redirected")
    where = [f"d.pdf_status IN ({','.join('?' for _ in statuses)})"]
    params: list[Any] = statuses[:]
    if company:
        where.append("p.company_name = ?")
        params.append(company)
    if not retry_failed:
        where.append("(d.local_path = '' OR d.local_path IS NULL)")
    if not include_suspicious:
        where.append("""
            lower(COALESCE(d.final_pdf_url, d.pdf_url)) NOT LIKE '%guide%'
            AND COALESCE(d.final_pdf_url, d.pdf_url) NOT LIKE '%導讀%'
            AND lower(COALESCE(d.final_pdf_url, d.pdf_url)) NOT LIKE '%reading-friendly%'
        """)

    sql = f"""
        SELECT
            d.id AS document_id,
            d.pdf_url,
            d.final_pdf_url,
            d.pdf_status,
            d.local_path,
            p.id AS product_db_id,
            p.product_id,
            p.company_name,
            p.product_name,
            p.category
        FROM policy_documents d
        JOIN insurance_products p ON p.id = d.product_db_id
        WHERE {' AND '.join(where)}
        ORDER BY p.company_name, p.product_id, d.id
        LIMIT ?
    """
    params.append(limit)
    with get_inventory_connection() as conn:
        return [row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


async def download_one(client: httpx.AsyncClient, doc: dict[str, Any], output_root: Path) -> dict[str, Any]:
    url = doc.get("final_pdf_url") or doc.get("pdf_url")
    company_dir = output_root / safe_segment(doc["company_name"])
    product_dir = company_dir / safe_segment(f"{doc['product_id']}_{doc['product_name']}")
    product_dir.mkdir(parents=True, exist_ok=True)
    target = product_dir / f"document_{doc['document_id']}.pdf"

    try:
        response = await client.get(url)
        response.raise_for_status()
        content_type = response.headers.get("content-type", "")
        content = response.content
        if not content.startswith(b"%PDF") and "pdf" not in content_type.lower():
            return {
                "document_id": doc["document_id"],
                "product_id": doc["product_id"],
                "company": doc["company_name"],
                "status": "non_pdf",
                "local_path": "",
                "checksum": "",
                "error": f"content-type={content_type}",
            }
        checksum = hashlib.sha256(content).hexdigest()
        target.write_bytes(content)
        rel_path = str(target.relative_to(ROOT)).replace("\\", "/")
        downloaded_at = datetime.now(timezone.utc).isoformat()
        with get_inventory_connection() as conn:
            conn.execute(
                """
                UPDATE policy_documents
                SET local_path = ?, checksum = ?, downloaded_at = ?, pdf_status = 'ok', updated_at = datetime('now')
                WHERE id = ?
                """,
                (rel_path, checksum, downloaded_at, doc["document_id"]),
            )
        return {
            "document_id": doc["document_id"],
            "product_id": doc["product_id"],
            "company": doc["company_name"],
            "status": "downloaded",
            "local_path": rel_path,
            "checksum": checksum,
            "bytes": len(content),
            "error": "",
        }
    except Exception as exc:
        with get_inventory_connection() as conn:
            conn.execute(
                "UPDATE policy_documents SET pdf_status = 'download_failed', updated_at = datetime('now') WHERE id = ?",
                (doc["document_id"],),
            )
        return {
            "document_id": doc["document_id"],
            "product_id": doc["product_id"],
            "company": doc["company_name"],
            "status": "failed",
            "local_path": "",
            "checksum": "",
            "error": str(exc)[:240],
        }


async def main_async(args: argparse.Namespace) -> None:
    docs = fetch_documents(args.limit, args.company, args.include_redirected, args.retry_failed, args.include_suspicious)
    args.output_root.mkdir(parents=True, exist_ok=True)
    timeout = httpx.Timeout(args.timeout)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.taiwanlife.com/",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers, verify=args.verify_ssl) as client:
        semaphore = asyncio.Semaphore(args.concurrency)

        async def run_one(doc: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await download_one(client, doc, args.output_root)

        results = await asyncio.gather(*(run_one(doc) for doc in docs))

    summary: dict[str, int] = {}
    for result in results:
        summary[result["status"]] = summary.get(result["status"], 0) + 1
    report = {
        "downloaded_at": datetime.now(timezone.utc).isoformat(),
        "total": len(results),
        "summary": summary,
        "items": results,
    }
    args.report.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({"report": str(args.report), "total": len(results), "summary": summary}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Download local PDF snapshots for audited policy documents.")
    parser.add_argument("--limit", type=int, default=25)
    parser.add_argument("--company")
    parser.add_argument("--include-redirected", action="store_true")
    parser.add_argument("--include-suspicious", action="store_true")
    parser.add_argument("--retry-failed", action="store_true")
    parser.add_argument("--concurrency", type=int, default=4)
    parser.add_argument("--timeout", type=float, default=20)
    parser.add_argument("--verify-ssl", action="store_true")
    parser.add_argument("--output-root", type=Path, default=DEFAULT_OUTPUT_ROOT)
    parser.add_argument("--report", type=Path, default=DEFAULT_REPORT)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
