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
from inventory_db import get_inventory_connection, row_to_dict

DEFAULT_OUTPUT = BACKEND / "data" / "product_link_audit.json"


def classify(
    status: str,
    content_type: str,
    final_url: str,
    original_url: str,
    *,
    expect_pdf: bool,
    body_preview: str = "",
) -> str:
    if "request rejected" in body_preview.lower():
        return "browser_required"
    if status in {"timeout", "network_error", "ssl_error"}:
        return "blocked"
    if not status.isdigit():
        return "unknown"
    code = int(status)
    if code in {401, 403, 429}:
        return "blocked"
    if code in {404, 410}:
        return "missing"
    if 300 <= code < 400 or (final_url and original_url and final_url.rstrip("/") != original_url.rstrip("/")):
        if expect_pdf and "pdf" in content_type.lower():
            return "ok"
        return "redirected"
    if 200 <= code < 300:
        if expect_pdf and "pdf" not in content_type.lower():
            return "non_pdf"
        return "ok"
    if code >= 500:
        return "unknown"
    return "unknown"


async def check_url(client: httpx.AsyncClient, url: str, *, expect_pdf: bool) -> dict[str, str]:
    if not url:
        return {"status": "no_url", "content_type": "", "final_url": "", "result": "missing", "error": "", "body_preview": ""}
    try:
        try:
            response = await client.head(url)
        except httpx.TransportError:
            response = await client.get(url, headers={"Range": "bytes=0-512"})
        if response.status_code in {403, 405}:
            response = await client.get(url, headers={"Range": "bytes=0-512"})
        content_type = response.headers.get("content-type", "")
        if "taiwanlife.com" in url.lower() and "text/html" in content_type.lower() and response.request.method == "HEAD":
            response = await client.get(url, headers={"Range": "bytes=0-2048"})
        status = str(response.status_code)
        content_type = response.headers.get("content-type", "")
        final_url = str(response.url)
        body_preview = ""
        if "text/html" in content_type.lower():
            body_preview = response.text[:500]
        return {
            "status": status,
            "content_type": content_type,
            "final_url": final_url,
            "result": classify(status, content_type, final_url, url, expect_pdf=expect_pdf, body_preview=body_preview),
            "error": "",
            "body_preview": body_preview,
        }
    except httpx.TimeoutException as exc:
        return {
            "status": "timeout",
            "content_type": "",
            "final_url": url,
            "result": "blocked",
            "error": str(exc)[:200],
            "body_preview": "",
        }
    except httpx.TransportError as exc:
        text = str(exc)
        status = "ssl_error" if "SSL" in text.upper() or "CERTIFICATE" in text.upper() else "network_error"
        return {
            "status": status,
            "content_type": "",
            "final_url": url,
            "result": "blocked",
            "error": text[:200],
            "body_preview": "",
        }
    except Exception as exc:
        return {
            "status": "error",
            "content_type": "",
            "final_url": url,
            "result": "unknown",
            "error": str(exc)[:200],
            "body_preview": "",
        }


def fetch_products(limit: int, company: str | None, only_unknown: bool) -> list[dict[str, Any]]:
    where = []
    params: list[Any] = []
    if company:
        where.append("p.company_name = ?")
        params.append(company)
    if only_unknown:
        where.append("(p.url_status = 'unknown' OR p.document_status = 'unknown')")
    clause = "WHERE " + " AND ".join(where) if where else ""
    sql = f"""
        SELECT
            p.id, p.product_id, p.company_name, p.product_name, p.source_url,
            d.pdf_url
        FROM insurance_products p
        LEFT JOIN policy_documents d ON d.product_db_id = p.id
        {clause}
        GROUP BY p.id
        ORDER BY p.company_name, p.id
        LIMIT ?
    """
    params.append(limit)
    with get_inventory_connection() as conn:
        return [row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


async def audit_product(client: httpx.AsyncClient, product: dict[str, Any]) -> dict[str, Any]:
    source = await check_url(client, product.get("source_url") or "", expect_pdf=False)
    pdf = await check_url(client, product.get("pdf_url") or "", expect_pdf=True)
    return {
        "product_db_id": product["id"],
        "product_id": product["product_id"],
        "company": product["company_name"],
        "product_name": product["product_name"],
        "source_url": product.get("source_url") or "",
        "source": source,
        "pdf_url": product.get("pdf_url") or "",
        "pdf": pdf,
    }


def persist_results(results: list[dict[str, Any]], output: Path) -> None:
    checked_at = datetime.now(timezone.utc).isoformat()
    with get_inventory_connection() as conn:
        for item in results:
            conn.execute(
                """
                INSERT INTO product_link_audits (
                    product_db_id, source_url, source_status, source_result, source_content_type,
                    final_source_url, pdf_url, pdf_status, pdf_result, pdf_content_type,
                    final_pdf_url, error, checked_at
                )
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    item["product_db_id"],
                    item["source_url"],
                    item["source"]["status"],
                    item["source"]["result"],
                    item["source"]["content_type"],
                    item["source"]["final_url"],
                    item["pdf_url"],
                    item["pdf"]["status"],
                    item["pdf"]["result"],
                    item["pdf"]["content_type"],
                    item["pdf"]["final_url"],
                    "; ".join(x for x in [item["source"]["error"], item["pdf"]["error"]] if x),
                    checked_at,
                ),
            )
            conn.execute(
                """
                UPDATE insurance_products
                SET url_status = ?, document_status = ?, final_source_url = ?, updated_at = datetime('now')
                WHERE id = ?
                """,
                (
                    item["source"]["result"],
                    item["pdf"]["result"],
                    item["source"]["final_url"],
                    item["product_db_id"],
                ),
            )
            if item["pdf_url"]:
                conn.execute(
                    """
                    UPDATE policy_documents
                    SET pdf_status = ?, final_pdf_url = ?, updated_at = datetime('now')
                    WHERE product_db_id = ? AND pdf_url = ?
                    """,
                    (item["pdf"]["result"], item["pdf"]["final_url"], item["product_db_id"], item["pdf_url"]),
                )

    summary: dict[str, dict[str, int]] = {"source": {}, "pdf": {}}
    for item in results:
        summary["source"][item["source"]["result"]] = summary["source"].get(item["source"]["result"], 0) + 1
        summary["pdf"][item["pdf"]["result"]] = summary["pdf"].get(item["pdf"]["result"], 0) + 1
    payload = {"checked_at": checked_at, "total": len(results), "summary": summary, "items": results}
    output.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")


async def main_async(args: argparse.Namespace) -> None:
    products = fetch_products(args.limit, args.company, args.only_unknown)
    timeout = httpx.Timeout(args.timeout)
    headers = {
        "User-Agent": "Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36",
        "Accept": "application/pdf,text/html,application/xhtml+xml,application/xml;q=0.9,*/*;q=0.8",
        "Accept-Language": "zh-TW,zh;q=0.9,en;q=0.8",
        "Referer": "https://www.taiwanlife.com/",
    }
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=headers, verify=args.verify_ssl) as client:
        semaphore = asyncio.Semaphore(args.concurrency)

        async def run_one(product: dict[str, Any]) -> dict[str, Any]:
            async with semaphore:
                return await audit_product(client, product)

        results = await asyncio.gather(*(run_one(product) for product in products))
    persist_results(results, args.output)
    print(json.dumps({"output": str(args.output), "total": len(results)}, ensure_ascii=False, indent=2))


def main() -> None:
    parser = argparse.ArgumentParser(description="Audit product page and PDF links.")
    parser.add_argument("--limit", type=int, default=50)
    parser.add_argument("--company")
    parser.add_argument("--only-unknown", action="store_true")
    parser.add_argument("--concurrency", type=int, default=5)
    parser.add_argument("--timeout", type=float, default=10)
    parser.add_argument("--verify-ssl", action="store_true")
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    asyncio.run(main_async(args))


if __name__ == "__main__":
    main()
