from inventory_db import get_inventory_connection

INSURANCE_KEYWORDS = [
    "住院",
    "手術",
    "癌症",
    "重大傷病",
    "意外",
    "失能",
    "長期照顧",
    "長照",
    "實支實付",
    "醫療費用",
    "理賠",
    "除外",
    "等待期",
    "豁免",
    "身故",
    "保險金",
]


def inventory_clause_summary() -> dict:
    with get_inventory_connection() as conn:
        totals = {
            "products": conn.execute("SELECT COUNT(*) FROM insurance_products").fetchone()[0],
            "documents": conn.execute("SELECT COUNT(*) FROM policy_documents").fetchone()[0],
            "downloaded_documents": conn.execute("SELECT COUNT(*) FROM policy_documents WHERE local_path != ''").fetchone()[0],
            "parsed_documents": conn.execute("SELECT COUNT(*) FROM policy_documents WHERE text_status = 'parsed'").fetchone()[0],
            "chunks": conn.execute("SELECT COUNT(*) FROM policy_document_chunks").fetchone()[0],
        }
        by_company = [
            dict(row)
            for row in conn.execute(
                """
                SELECT
                    p.company_name,
                    COUNT(DISTINCT p.id) AS products,
                    COUNT(DISTINCT CASE WHEN d.text_status = 'parsed' THEN d.id END) AS parsed_documents,
                    COUNT(c.id) AS chunks
                FROM insurance_products p
                LEFT JOIN policy_documents d ON d.product_db_id = p.id
                LEFT JOIN policy_document_chunks c ON c.document_id = d.id
                GROUP BY p.company_name
                ORDER BY parsed_documents DESC, p.company_name
                """
            ).fetchall()
        ]
        text_status = [
            dict(row)
            for row in conn.execute(
                """
                SELECT text_status, COUNT(*) AS documents
                FROM policy_documents
                GROUP BY text_status
                ORDER BY documents DESC
                """
            ).fetchall()
        ]
    return {"totals": totals, "by_company": by_company, "text_status": text_status}


def search_clauses(
    keyword: str,
    company: str | None = None,
    category: str | None = None,
    limit: int = 10,
) -> list[dict]:
    clauses = []
    if not keyword.strip():
        return clauses

    raw_terms = [term.strip() for term in keyword.split() if term.strip()]
    matched_keywords = [term for term in INSURANCE_KEYWORDS if term in keyword]
    terms = matched_keywords or raw_terms or [keyword.strip()]
    where = ["d.text_status = 'parsed'"]
    params: list[str | int] = []
    term_clauses = []
    for term in terms[:4]:
        term_clauses.append("c.text LIKE ?")
        params.append(f"%{term}%")
    if term_clauses:
        where.append("(" + " OR ".join(term_clauses) + ")")
    if company:
        where.append("p.company_name = ?")
        params.append(company)
    if category:
        where.append("p.category = ?")
        params.append(category)

    sql = f"""
        SELECT
            p.product_id,
            p.company_name AS company,
            p.product_name,
            p.category,
            d.id AS document_id,
            d.local_path,
            c.chunk_index,
            c.text
        FROM policy_document_chunks c
        JOIN policy_documents d ON d.id = c.document_id
        JOIN insurance_products p ON p.id = c.product_db_id
        WHERE {' AND '.join(where)}
        ORDER BY
            CASE WHEN c.text LIKE ? THEN 0 ELSE 1 END,
            LENGTH(c.text) ASC
        LIMIT ?
    """
    params.extend([f"%{keyword.strip()}%", limit])
    with get_inventory_connection() as conn:
        rows = conn.execute(sql, params).fetchall()
    return [dict(row) for row in rows]


def format_clause_context(items: list[dict]) -> str:
    if not items:
        return ""
    lines = [
        "【條款資料庫片段】以下內容來自已下載並解析的保單條款 PDF，回答時請優先依據這些片段；若不足以判斷，請明確說需要確認完整條款。"
    ]
    for index, item in enumerate(items, 1):
        excerpt = item["text"][:900].strip()
        lines.append(
            f"\n{index}. {item['product_name']}｜{item['company']}｜{item['category']}｜chunk {item['chunk_index']}\n{excerpt}"
        )
    return "\n".join(lines)
