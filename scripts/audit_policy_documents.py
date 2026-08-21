import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

ROOT = Path(__file__).resolve().parents[1]
BACKEND = ROOT / "backend"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))

import httpx
from audit_product_links import check_url
from inventory_db import get_inventory_connection, row_to_dict

DEFAULT_OUTPUT = BACKEND / "data" / "policy_document_audit.json"


def fetch_documents(limit: int, company: str | None, only_unknown: bool) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []
    if company:
        where.append("p.company_name = ?")
        params.append(company)
    if only_unknown:
        where.append("d.pdf_status = 'unknown'")
    clause = "WHERE " + " AND ".join(where) if where else ""
    sql = f"""
        SELECT
            d.id AS document_id,
            d.pdf_url,
            p.id AS product_db_id,
            p.product_id,
            p.company_name,
            p.product_name
        FROM policy_documents d
        JOIN insurance_products p ON p.id = d.product_db_id
        {clause}
        ORDER BY p.company_name, p.product_id, d.id
        LIMIT ?
    """
    params.append(limit)
    with get_inventory_connection() as conn:
        return [row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


def recompute_product_document_status(conn, product_db_id: int) -> None:
    statuses = [row["pdf_status"] for row in conn.execute(
        "SELECT pdf_status FROM policy_documents WHERE product_db_id = ?",
        (product_db_id,),
    ).fetchall()]
    if "ok" in statuses:
        status = "ok"
    elif "redirected" in statuses:
        status = "redirected"
    elif "blocked" in statuses:
        status = "blocked"
    elif "non_pdf" in statuses:
        status = "non_pdf"
    elif statuses:
        status = statuses[0]
    else:
        status = "missing"
    conn.execute(
        "UPDATE insurance_products SET document_status = ?, updated_at = datetime('now') WHERE id = ?",
        (status, product_db_id),
    )


async def audit_doc(client: httpx.AsyncClient, doc: dict[str, Any]) -> dict[str, Any]:
    result = await check_url(client, doc["pdf_url"], expect_pdf=True)
    return {**doc, "audit": result}


def persist(results: list[dict[str, Any]], output: Path) -> None:
    checked_at = datetime.now(timezone.utc).isoformat()
    touched_products = set()
    with get_inventory_connection() as conn:
        for item in results:
            conn.execute(
                """
                UPDATE policy_documents
                SET pdf_status = ?, final_pdf_url = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (item["audit"]["result"], item["audit"]["final_url"], item["document_id"]),
            )
            touched_products.add(item["product_db_id"])
        for product_db_id in touched_products:
            recompute_product_document_status(conn, product_db_id)

    summary: dict[str, int] = {}
    for item in results:
        summary[item["audit"]["result"]] = summary.get(item["audit"]["result"], 0) + 1
    output.write_text(
        json.dumps({"checked_at": checked_at, "total": len(results), "summary": summary, "items": results}, ensure_ascii=False, indent=2),
        encoding="utf-8",
    )


async def main_async(args: argparse.Namespace) -> None:
    docs = fetch_documents(args.limit, args.company, args.only_unknown)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.taiwanlife.com/",
    }
    async with httpx.AsyncClient(
        timeout=httpx.Timeout(args.timeout),
        follow_redirects=True,
        headers=headers,
        verify=args.verify_ssl,
    ) as client:
        semaphore = asyncio.Semaphore(args.concurrency)

        async def run_one(doc: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await audit_doc(client, doc)

        results = await asyncio.gather(*(run_one(doc) for doc in docs))
    persist(results, args.output)
    print(json.dumps({"output": str(args.output), "total": len(results)}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit every policy document URL, not only one URL per product.")
    parser.add_argument("--limit", type=int, default=2000)
    parser.add_argument("--company")
    parser.add_argument("--only-unknown", action="store_true")
    parser.add_argument("--concurrency", type=int, default=8)
    parser.add_argument("--timeout", type=float, default=15)
    parser.add_argument("--verify-ssl", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
