import json
import time
from pathlib import Path
from inventory_db import get_inventory_connection, row_to_dict

DATA_PATH = Path(__file__).parent.parent / "data" / "crawled_products_with_pdf_dm_links.json"


def get_products() -> list[dict]:
    inventory_products = get_inventory_products()
    if inventory_products:
        return inventory_products
    with open(DATA_PATH, encoding="utf-8") as f:
        data = json.load(f)
    return data["products"]


def get_inventory_products() -> list[dict]:
    # A database error must surface, not silently replace the inventory with
    # the legacy 780-product file. Read again after transient failures.
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


# --- Paginated, database-side queries (used by the API and the AI retrieval) ---
# get_products() / search_products() above load the whole catalogue; they are
# kept for existing callers and tests, but the routers use the functions below.

# Product queries run inside the database with LIMIT/OFFSET -- never load the
# whole catalogue into memory. With the TII full index there are ~130k
# products; the old "read everything, filter in Python, lru_cache it" approach
# made the first request take minutes and held the lot in RAM.

_PRODUCT_COLUMNS = """
    p.id AS db_id, p.product_id, p.product_name, p.company_name AS company, p.category, p.currency,
    p.status, p.source, p.source_url, p.final_source_url, p.url_status, p.document_status
"""

_CACHE_TTL_SECONDS = 600
_cache: dict[str, tuple[float, object]] = {}


def _cached(key: str, loader):
    hit = _cache.get(key)
    if hit and time.monotonic() - hit[0] < _CACHE_TTL_SECONDS:
        return hit[1]
    value = loader()
    _cache[key] = (time.monotonic(), value)
    return value


def _like(conn) -> str:
    return "ILIKE" if getattr(conn, "dialect", "sqlite") == "postgres" else "LIKE"


COVERAGE_TYPES = ("life", "cancer", "critical", "accident", "daily", "medical", "ltc")


def load_attributes(conn, product_db_ids: list[int]) -> dict[int, dict]:
    """Structured facts extracted from each product's clauses
    (scripts/extract_product_attributes.py -> product_attributes). Products
    without clause documents simply have no entry."""
    if not product_db_ids:
        return {}
    placeholders = ", ".join("?" for _ in product_db_ids)
    rows = conn.execute(
        f"SELECT product_db_id, attributes FROM product_attributes WHERE product_db_id IN ({placeholders})",
        list(product_db_ids),
    ).fetchall()
    return {r[0]: json.loads(r[1] or "{}") for r in rows}


def coverage_summary(attrs: dict | None) -> dict | None:
    """Compact view for lists / chat context (the full record is on the
    product detail endpoint)."""
    if not attrs:
        return None
    return {
        "types": attrs.get("coverage_types") or [],
        "is_rider": attrs.get("is_rider"),
        "currency": attrs.get("currency"),
        "issue_age": attrs.get("issue_age"),
        "coverage_period": attrs.get("coverage_period"),
        "payment_terms": attrs.get("payment_terms") or [],
        "waiting_periods": attrs.get("waiting_periods") or [],
        "benefit_names": [b.get("name") for b in attrs.get("benefits") or [] if b.get("name")][:8],
        "exclusion_count": len(attrs.get("exclusions") or []),
    }


def _attach_download_urls(conn, products: list[dict], full_attributes: bool = False) -> list[dict]:
    ids = [p["db_id"] for p in products]
    urls: dict[int, list[str]] = {i: [] for i in ids}
    if ids:
        placeholders = ", ".join("?" for _ in ids)
        # Clause documents first: the card's 「條款」 button and 白話解釋 use
        # download_urls[0], which used to be whichever document was stored
        # first (often a DM or rate table).
        for row in conn.execute(
            f"SELECT product_db_id, pdf_url FROM policy_documents "
            f"WHERE pdf_url IS NOT NULL AND product_db_id IN ({placeholders}) "
            f"ORDER BY CASE WHEN document_type IN ('terms', 'POLICY_TERMS') THEN 0 ELSE 1 END, id",
            ids,
        ).fetchall():
            urls[row[0]].append(row[1])
    attributes = load_attributes(conn, ids)
    for p in products:
        p["download_urls"] = urls.get(p["db_id"], [])
        attrs = attributes.get(p["db_id"])
        p["coverage"] = coverage_summary(attrs)
        if full_attributes:
            p["attributes"] = attrs
        p.pop("db_id", None)
    return products


def query_products(
    category: str | None = None,
    company: str | None = None,
    keyword: str | None = None,
    status: str | None = None,
    coverage_type: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> tuple[int, list[dict]]:
    """Filtered, paginated product listing. Returns (total, page_rows)."""
    with get_inventory_connection() as conn:
        where, params = [], []
        if coverage_type in COVERAGE_TYPES:
            if getattr(conn, "dialect", "sqlite") == "postgres":
                where.append(
                    "EXISTS (SELECT 1 FROM product_attributes a WHERE a.product_db_id = p.id "
                    "AND (a.attributes::jsonb -> 'coverage_types') @> jsonb_build_array(?::text))"
                )
            else:
                where.append(
                    "EXISTS (SELECT 1 FROM product_attributes a, json_each(a.attributes, '$.coverage_types') j "
                    "WHERE a.product_db_id = p.id AND j.value = ?)"
                )
            params.append(coverage_type)
        if category:
            where.append("p.category = ?")
            params.append(category)
        if company:
            where.append("p.company_name = ?")
            params.append(company)
        if status:
            where.append("p.status = ?")
            params.append(status)
        if keyword and keyword.strip():
            like = _like(conn)
            where.append(f"(p.product_name {like} ? OR p.company_name {like} ?)")
            kw = f"%{keyword.strip()}%"
            params.extend([kw, kw])
        where_sql = f"WHERE {' AND '.join(where)}" if where else ""

        total = conn.execute(f"SELECT COUNT(*) FROM insurance_products p {where_sql}", params).fetchone()[0]
        # Products that actually have clause documents (company crawls / IB)
        # first, then on-sale before discontinued, so a bare browse starts
        # with the most useful rows rather than 94k discontinued TII entries.
        rows = conn.execute(
            f"""
            SELECT {_PRODUCT_COLUMNS}
            FROM insurance_products p
            {where_sql}
            ORDER BY
                CASE WHEN p.source = 'tii' THEN 1 ELSE 0 END,
                CASE WHEN p.status = 'discontinued' THEN 1 ELSE 0 END,
                p.company_name, p.product_name
            LIMIT ? OFFSET ?
            """,
            [*params, page_size, (page - 1) * page_size],
        ).fetchall()
        products = _attach_download_urls(conn, [row_to_dict(r) for r in rows])
    return total, products


def get_product_by_id(product_id: str) -> dict | None:
    with get_inventory_connection() as conn:
        row = conn.execute(
            f"SELECT {_PRODUCT_COLUMNS} FROM insurance_products p WHERE p.product_id = ? "
            "ORDER BY CASE WHEN p.source = 'tii' THEN 1 ELSE 0 END LIMIT 1",
            (product_id,),
        ).fetchone()
        if row is None:
            return None
        return _attach_download_urls(conn, [row_to_dict(row)], full_attributes=True)[0]


def list_categories() -> list[str]:
    def load():
        with get_inventory_connection() as conn:
            cats = [r[0] for r in conn.execute("SELECT DISTINCT category FROM insurance_products").fetchall()]
        cats = sorted(c for c in cats if c)
        return [c for c in cats if c not in ("其他", "產險其他")] + [c for c in ("其他", "產險其他") if c in cats]

    return _cached("categories", load)


def list_companies() -> list[str]:
    def load():
        with get_inventory_connection() as conn:
            names = [r[0] for r in conn.execute("SELECT DISTINCT company_name FROM insurance_products").fetchall()]
        known = sorted(n for n in names if n and n != "公司未知")
        return known + (["公司未知"] if "公司未知" in names else [])

    return _cached("companies", load)


def get_product_inventory_summary() -> dict:
    with get_inventory_connection() as conn:
        product_count = conn.execute("SELECT COUNT(*) AS c FROM insurance_products").fetchone()["c"]
        company_count = conn.execute("SELECT COUNT(*) AS c FROM insurance_companies").fetchone()["c"]
        document_count = conn.execute("SELECT COUNT(*) AS c FROM policy_documents").fetchone()["c"]
        parsed_document_count = conn.execute(
            "SELECT COUNT(*) AS c FROM policy_documents WHERE text_status = 'parsed'"
        ).fetchone()["c"]
        downloaded_document_count = conn.execute(
            # Production blanks local_path (raw files stay on the operator's
            # PC), so "parsed" also counts as downloaded.
            "SELECT COUNT(*) AS c FROM policy_documents WHERE COALESCE(local_path, '') <> '' OR text_status = 'parsed'"
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
        # One aggregate pass per table, grouped by (company_id, company_name),
        # then attributed to companies in Python. The previous version ran 8
        # correlated subqueries per company with OR conditions (no index use)
        # -- ~50 s once the catalogue reached ~130k products.
        downloaded_expr = "(COALESCE(d.local_path, '') <> '' OR d.text_status = 'parsed')"
        product_groups = conn.execute(
            "SELECT company_id, company_name, COUNT(*), MAX(updated_at) FROM insurance_products GROUP BY company_id, company_name"
        ).fetchall()
        doc_groups = {
            (r[0], r[1]): r[2:]
            for r in conn.execute(
                f"""
                SELECT p.company_id, p.company_name, COUNT(d.id),
                       SUM(CASE WHEN {downloaded_expr} THEN 1 ELSE 0 END),
                       SUM(CASE WHEN d.text_status = 'parsed' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN d.text_status = 'pending' THEN 1 ELSE 0 END),
                       SUM(CASE WHEN d.pdf_status = 'browser_required' THEN 1 ELSE 0 END)
                FROM policy_documents d JOIN insurance_products p ON d.product_db_id = p.id
                GROUP BY p.company_id, p.company_name
                """
            ).fetchall()
        }
        chunk_groups = {
            (r[0], r[1]): r[2]
            for r in conn.execute(
                """
                SELECT p.company_id, p.company_name, COUNT(*)
                FROM policy_document_chunks ch JOIN insurance_products p ON ch.product_db_id = p.id
                GROUP BY p.company_id, p.company_name
                """
            ).fetchall()
        }
        company_status = []
        for c in conn.execute(
            "SELECT id, slug, short_name, name, type, status FROM insurance_companies"
        ).fetchall():
            cid, slug, short_name, name, ctype, cstatus = c[0], c[1], c[2], c[3], c[4], c[5]
            totals = dict(products=0, documents=0, downloaded_documents=0, parsed_documents=0,
                          pending_documents=0, browser_required_documents=0, chunks=0)
            updated_at = None
            for gid, gname, count, max_updated in product_groups:
                if gid != cid and gname not in (short_name, name):
                    continue
                totals["products"] += count
                updated_at = max(filter(None, (updated_at, max_updated)), default=None)
                docs = doc_groups.get((gid, gname))
                if docs:
                    for key, value in zip(
                        ("documents", "downloaded_documents", "parsed_documents", "pending_documents",
                         "browser_required_documents"),
                        docs,
                    ):
                        totals[key] += value or 0
                totals["chunks"] += chunk_groups.get((gid, gname), 0) or 0
            company_status.append(
                {"slug": slug, "company": short_name, "company_name": name, "type": ctype,
                 "company_status": cstatus, **totals, "updated_at": updated_at}
            )
        company_status.sort(key=lambda r: (r["type"], -r["products"], r["company"]))
        by_type_acc: dict[str, dict] = {}
        for r in company_status:
            t = by_type_acc.setdefault(r["type"], {"type": r["type"], "companies": 0, "covered_companies": 0,
                                                   "products": 0, "documents": 0, "parsed_documents": 0})
            t["companies"] += 1
            t["covered_companies"] += 1 if r["products"] else 0
            for key in ("products", "documents", "parsed_documents"):
                t[key] += r[key]
        by_type = [by_type_acc[k] for k in sorted(by_type_acc)]
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
