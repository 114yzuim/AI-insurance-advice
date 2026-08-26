import json
from pathlib import Path
from functools import lru_cache
from inventory_db import get_inventory_connection, row_to_dict

DATA_PATH = Path(__file__).parent.parent / "data" / "crawled_products_with_pdf_dm_links.json"


@lru_cache(maxsize=1)
def get_products() -> list[dict]:
    inventory_products = get_inventory_products()
    if inventory_products:
        return inventory_products
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["products"]


def get_inventory_products() -> list[dict]:
    try:
        with get_inventory_connection() as conn:
            rows = conn.execute(
                """
                SELECT
                    p.product_id, p.product_name, p.company_name AS company, p.category, p.currency,
                    p.source_url, p.final_source_url, p.status, p.url_status, p.document_status,
                    COALESCE(
                        json_group_array(d.pdf_url) FILTER (WHERE d.pdf_url IS NOT NULL),
                        '[]'
                    ) AS download_urls
                FROM insurance_products p
                LEFT JOIN policy_documents d ON d.product_db_id = p.id
                GROUP BY p.id
                ORDER BY p.company_name, p.product_name
                """
            ).fetchall()
        return [row_to_dict(row) for row in rows]
    except Exception:
        return []


def search_products(
    category: str | None = None,
    company: str | None = None,
    keyword: str | None = None,
) -> list[dict]:
    results = get_products()
    if category:
        results = [p for p in results if p["category"] == category]
    if company:
        results = [p for p in results if p["company"] == company]
    if keyword:
        kw = keyword.lower()
        results = [
            p for p in results
            if kw in p["product_name"].lower() or kw in p.get("company", "").lower()
        ]
    return results


def get_product_inventory_summary() -> dict:
    with get_inventory_connection() as conn:
        product_count = conn.execute("SELECT COUNT(*) AS c FROM insurance_products").fetchone()["c"]
        company_count = conn.execute("SELECT COUNT(*) AS c FROM insurance_companies").fetchone()["c"]
        document_count = conn.execute("SELECT COUNT(*) AS c FROM policy_documents").fetchone()["c"]
        parsed_document_count = conn.execute(
            "SELECT COUNT(*) AS c FROM policy_documents WHERE text_status = 'parsed'"
        ).fetchone()["c"]
        downloaded_document_count = conn.execute(
            "SELECT COUNT(*) AS c FROM policy_documents WHERE COALESCE(local_path, '') <> ''"
        ).fetchone()["c"]
        chunk_count = conn.execute("SELECT COUNT(*) AS c FROM policy_document_chunks").fetchone()["c"]
        by_company = [
            dict(row)
            for row in conn.execute(
                """
                SELECT company_name AS company, COUNT(*) AS count
                FROM insurance_products
                GROUP BY company_name
                ORDER BY count DESC, company_name
                """
            ).fetchall()
        ]
        company_status = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    c.slug,
                    c.short_name AS company,
                    c.name AS company_name,
                    c.type,
                    c.status AS company_status,
                    (
                        SELECT COUNT(*)
                        FROM insurance_products p
                        WHERE p.company_id = c.id
                           OR p.company_name = c.short_name
                           OR p.company_name = c.name
                    ) AS products,
                    (
                        SELECT COUNT(*)
                        FROM policy_documents d
                        JOIN insurance_products p ON d.product_db_id = p.id
                        WHERE p.company_id = c.id
                           OR p.company_name = c.short_name
                           OR p.company_name = c.name
                    ) AS documents,
                    (
                        SELECT COUNT(*)
                        FROM policy_documents d
                        JOIN insurance_products p ON d.product_db_id = p.id
                        WHERE COALESCE(d.local_path, '') <> ''
                          AND (
                            p.company_id = c.id
                            OR p.company_name = c.short_name
                            OR p.company_name = c.name
                          )
                    ) AS downloaded_documents,
                    (
                        SELECT COUNT(*)
                        FROM policy_documents d
                        JOIN insurance_products p ON d.product_db_id = p.id
                        WHERE d.text_status = 'parsed'
                          AND (
                            p.company_id = c.id
                            OR p.company_name = c.short_name
                            OR p.company_name = c.name
                          )
                    ) AS parsed_documents,
                    (
                        SELECT COUNT(*)
                        FROM policy_documents d
                        JOIN insurance_products p ON d.product_db_id = p.id
                        WHERE d.text_status = 'pending'
                          AND (
                            p.company_id = c.id
                            OR p.company_name = c.short_name
                            OR p.company_name = c.name
                          )
                    ) AS pending_documents,
                    (
                        SELECT COUNT(*)
                        FROM policy_documents d
                        JOIN insurance_products p ON d.product_db_id = p.id
                        WHERE d.pdf_status = 'browser_required'
                          AND (
                            p.company_id = c.id
                            OR p.company_name = c.short_name
                            OR p.company_name = c.name
                          )
                    ) AS browser_required_documents,
                    (
                        SELECT COUNT(*)
                        FROM policy_document_chunks ch
                        JOIN insurance_products p ON ch.product_db_id = p.id
                        WHERE p.company_id = c.id
                           OR p.company_name = c.short_name
                           OR p.company_name = c.name
                    ) AS chunks,
                    (
                        SELECT MAX(p.updated_at)
                        FROM insurance_products p
                        WHERE p.company_id = c.id
                           OR p.company_name = c.short_name
                           OR p.company_name = c.name
                    ) AS updated_at
                FROM insurance_companies c
                ORDER BY c.type, products DESC, c.short_name
                """
            ).fetchall()
        ]
        by_type = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    c.type,
                    COUNT(DISTINCT c.id) AS companies,
                    COUNT(DISTINCT CASE WHEN p.id IS NOT NULL THEN c.id END) AS covered_companies,
                    COUNT(DISTINCT p.id) AS products,
                    COUNT(d.id) AS documents,
                    SUM(CASE WHEN d.text_status = 'parsed' THEN 1 ELSE 0 END) AS parsed_documents
                FROM insurance_companies c
                LEFT JOIN insurance_products p
                    ON p.company_id = c.id
                    OR p.company_name = c.short_name
                    OR p.company_name = c.name
                LEFT JOIN policy_documents d ON d.product_db_id = p.id
                GROUP BY c.type
                ORDER BY c.type
                """
            ).fetchall()
        ]
        by_audit = [
            dict(row)
            for row in conn.execute(
                """
                SELECT url_status, document_status, COUNT(*) AS count
                FROM insurance_products
                GROUP BY url_status, document_status
                ORDER BY count DESC
                """
            ).fetchall()
        ]
        by_text_status = [
            dict(row)
            for row in conn.execute(
                """
                SELECT text_status, COUNT(*) AS count
                FROM policy_documents
                GROUP BY text_status
                ORDER BY count DESC, text_status
                """
            ).fetchall()
        ]
        by_pdf_status = [
            dict(row)
            for row in conn.execute(
                """
                SELECT pdf_status, COUNT(*) AS count
                FROM policy_documents
                GROUP BY pdf_status
                ORDER BY count DESC, pdf_status
                """
            ).fetchall()
        ]
    normalized_companies = []
    for company in company_status:
        products = company["products"] or 0
        documents = company["documents"] or 0
        parsed = company["parsed_documents"] or 0
        browser_required = company["browser_required_documents"] or 0
        if products == 0:
            inventory_status = "missing"
            action = "待補官方來源"
        elif browser_required and parsed == 0:
            inventory_status = "browser_required"
            action = "待瀏覽器下載/解析"
        elif documents and parsed >= documents:
            inventory_status = "ready"
            action = "可用"
        else:
            inventory_status = "partial"
            action = "部分可用，待補解析"
        normalized_companies.append(
            {
                **company,
                "products": products,
                "documents": documents,
                "downloaded_documents": company["downloaded_documents"] or 0,
                "parsed_documents": parsed,
                "pending_documents": company["pending_documents"] or 0,
                "browser_required_documents": browser_required,
                "chunks": company["chunks"] or 0,
                "inventory_status": inventory_status,
                "action": action,
            }
        )

    remaining_gaps = [
        {
            "company": "安聯人壽",
            "reason": "官方商品站有瀏覽器/安全驗證，普通 HTTP adapter 會被擋。",
            "next_step": "使用 browser flow 或官方匯出檔。",
        },
        {
            "company": "臺銀人壽",
            "reason": "官方頁面目前回傳空殼內容，商品與條款列表尚未定位。",
            "next_step": "使用 browser flow 建立商品頁導覽規則。",
        },
        {
            "company": "元大人壽",
            "reason": "官方 PDF 分散，產品與 PDF 對應關係尚不穩定。",
            "next_step": "用 browser flow 建立產品頁導覽規則。",
        },
        {
            "company": "台灣人壽",
            "reason": "已有商品與文件 URL，但 PDF 下載需要瀏覽器流程。",
            "next_step": "補 browser downloader 或請官方提供條款檔。",
        },
    ]
    return {
        "companies": company_count,
        "products": product_count,
        "documents": document_count,
        "downloaded_documents": downloaded_document_count,
        "parsed_documents": parsed_document_count,
        "chunks": chunk_count,
        "by_company": by_company,
        "company_status": normalized_companies,
        "by_type": by_type,
        "by_audit": by_audit,
        "by_text_status": by_text_status,
        "by_pdf_status": by_pdf_status,
        "remaining_gaps": remaining_gaps,
    }
