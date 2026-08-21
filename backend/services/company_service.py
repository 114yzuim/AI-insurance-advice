import json
from inventory_db import get_inventory_connection, row_to_dict


def list_companies(company_type: str | None = None) -> list[dict]:
    sql = """
        SELECT id, slug, name, short_name, type, status, former_names, official_url, source_url, updated_at
        FROM insurance_companies
    """
    params: list[str] = []
    if company_type:
        sql += " WHERE type = ?"
        params.append(company_type)
    sql += " ORDER BY type, short_name"
    with get_inventory_connection() as conn:
        return [row_to_dict(row) for row in conn.execute(sql, params).fetchall()]


def upsert_company(payload: dict) -> dict:
    with get_inventory_connection() as conn:
        conn.execute(
            """
            INSERT INTO insurance_companies (
                slug, name, short_name, type, status, former_names, official_url, source_url, updated_at
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, datetime('now'))
            ON CONFLICT(slug) DO UPDATE SET
                name=excluded.name,
                short_name=excluded.short_name,
                type=excluded.type,
                status=excluded.status,
                former_names=excluded.former_names,
                official_url=excluded.official_url,
                source_url=excluded.source_url,
                updated_at=datetime('now')
            """,
            (
                payload["slug"],
                payload["name"],
                payload["short_name"],
                payload["type"],
                payload.get("status", "active"),
                json.dumps(payload.get("former_names", []), ensure_ascii=False),
                payload.get("official_url", ""),
                payload.get("source_url", ""),
            ),
        )
        row = conn.execute("SELECT * FROM insurance_companies WHERE slug = ?", (payload["slug"],)).fetchone()
        return row_to_dict(row)
