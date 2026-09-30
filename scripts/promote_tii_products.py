"""Promote TII full-index records into insurance_products, so the product
search API and the AI retrieval (which only read insurance_products) can
see them.

scripts/sync_document_registry_to_policy_documents.py only bridges products
that have a downloaded document; the TII full index has no documents at all
(the per-product DetailList.aspx is CAPTCHA-gated), so without this step
those ~128k products would stay in source_product_records forever.

Pipeline position (run after these):
    scripts/resolve_tii_companies.py     -> company_name from product name
    scripts/import_source_records.py     -> source_product_records
    scripts/reconcile_source_records.py  -> product_families / product_versions

What it does, idempotently (safe to re-run after a new crawl):
  1. Adds any company the resolver produced that insurance_companies doesn't
     have yet (status 'listed_in_tii' -- many are merged/defunct insurers,
     kept under their printed-era name, see company_resolver.py).
  2. For each TII record, looks for an existing non-TII product with the same
     normalized (company, product name) -- also trying the name with the
     company prefix stripped, since company sites usually omit it. A match is
     NOT duplicated: the TII fields are attached to that product's
     metadata["tii"] instead.
  3. Otherwise upserts an insurance_products row: source='tii',
     product_id=TII productId, category from scripts/product_category.py,
     status active/discontinued from 停售日, document_status='none'.
     Records whose company could not be resolved are kept, under
     company_name '公司未知'.
  4. --recategorize-ib: IB disclosure products were imported with the raw
     category 'property' and the company's full legal name; give them the
     same inferred categories and short company name as everything else.

Usage:
    python scripts/promote_tii_products.py [--dry-run] [--recategorize-ib]
"""

from __future__ import annotations

import argparse
import hashlib
import json
import re
import sys
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))
sys.path.insert(0, str(ROOT / "scripts"))
sys.path.insert(0, str(ROOT / "scripts" / "sources" / "tii"))

from inventory_db import get_inventory_connection  # noqa: E402
from inventory_repository import normalize_company_name, normalize_product_name  # noqa: E402
from product_category import infer_category  # noqa: E402
from company_resolver import CANONICAL_COMPANIES  # noqa: E402

UNKNOWN_COMPANY = "公司未知"
_ROC_DATE_RE = re.compile(r"^(\d{2,3})/(\d{1,2})/(\d{1,2})$")


def roc_to_iso(value: str) -> str:
    match = _ROC_DATE_RE.match((value or "").strip())
    if not match:
        return ""
    year, month, day = (int(g) for g in match.groups())
    return f"{year + 1911:04d}-{month:02d}-{day:02d}"


def _key(company: str, product: str) -> str:
    return f"{normalize_company_name(company)}::{normalize_product_name(product)}"


def _ensure_companies(conn, dry_run: bool) -> tuple[dict[str, int], list[str]]:
    by_short = {row[1]: row[0] for row in conn.execute("SELECT id, short_name FROM insurance_companies").fetchall()}
    added = []
    for short_name, company_type in CANONICAL_COMPANIES.items():
        if short_name in by_short:
            continue
        added.append(short_name)
        if dry_run:
            continue
        slug = "tii-" + hashlib.sha1(short_name.encode("utf-8")).hexdigest()[:10]
        row = conn.execute(
            """
            INSERT INTO insurance_companies (slug, name, short_name, type, status, source_url)
            VALUES (?, ?, ?, ?, 'listed_in_tii', 'https://insprod.tii.org.tw/ResultQueryAll.aspx')
            RETURNING id
            """,
            (slug, short_name, short_name, company_type),
        ).fetchone()
        by_short[short_name] = row[0]
    return by_short, added


def run(dry_run: bool, recategorize_ib: bool) -> dict:
    stats: Counter = Counter()
    with get_inventory_connection() as conn:
        company_ids, companies_added = _ensure_companies(conn, dry_run)

        existing: dict[str, int] = {}
        existing_meta: dict[int, tuple[str, str]] = {}
        for row in conn.execute(
            "SELECT id, company_name, product_name, metadata, status FROM insurance_products WHERE source <> 'tii'"
        ).fetchall():
            existing.setdefault(_key(row[1], row[2]), row[0])
            existing_meta[row[0]] = (row[3], row[4])

        tii_rows = {
            row[0]: row[1]
            for row in conn.execute("SELECT product_id, id FROM insurance_products WHERE source = 'tii'").fetchall()
        }

        records = conn.execute(
            """
            SELECT spr.id, spr.source_product_id, spr.source_product_url, spr.company_name, spr.product_name,
                   spr.sale_start_date, spr.sale_end_date, spr.raw_payload
            FROM source_product_records spr
            JOIN inventory_sources s ON s.id = spr.source_id
            WHERE s.code = 'tii'
            ORDER BY spr.id
            """
        ).fetchall()

        merged_into: dict[int, list[dict]] = {}
        for rec_id, tii_id, url, company, name, sale_start, sale_end, raw in records:
            payload = json.loads(raw or "{}")
            raw_fields = payload.get("raw_fields") or {}
            resolution = raw_fields.get("company_resolution") or {}
            company_type = payload.get("company_type") or ""
            stop_text = raw_fields.get("停售日", sale_end or "")
            discontinued = bool(stop_text) and stop_text != "未停售"
            tii_info = {
                "source_product_record_id": rec_id,
                "tii_product_id": tii_id,
                "detail_url": url,
                "sale_start_date": sale_start,
                "sale_start_date_iso": roc_to_iso(sale_start),
                "sale_end_date": "" if not discontinued else stop_text,
                "sale_end_date_iso": roc_to_iso(stop_text) if discontinued else "",
                "company_resolution": resolution,
                "company_type": company_type,
            }

            match_id = None
            if company:
                match_id = existing.get(_key(company, name))
                literal = resolution.get("matched") or ""
                if match_id is None and literal and name.startswith(literal):
                    match_id = existing.get(_key(company, name[len(literal):]))
            if match_id is not None:
                merged_into.setdefault(match_id, []).append(tii_info)
                stats["merged_into_existing"] += 1
                continue

            company_name = company or UNKNOWN_COMPANY
            values = {
                "product_id": tii_id,
                "company_id": company_ids.get(company) if company else None,
                "company_name": company_name,
                "product_name": name,
                "category": infer_category(name, company_type),
                "status": "discontinued" if discontinued else "active",
                "source_url": url,
                "document_status": "none",
                "is_historical": 1 if discontinued else 0,
                "metadata": json.dumps({"tii": tii_info}, ensure_ascii=False),
            }
            stats["discontinued" if discontinued else "active"] += 1
            stats["unknown_company" if not company else "known_company"] += 1
            if dry_run:
                stats["would_upsert"] += 1
                continue
            existing_id = tii_rows.get(tii_id)
            if existing_id is None:
                conn.execute(
                    f"""
                    INSERT INTO insurance_products (source, {', '.join(values)})
                    VALUES ('tii', {', '.join('?' for _ in values)})
                    """,
                    tuple(values.values()),
                )
                stats["inserted"] += 1
            else:
                conn.execute(
                    f"""
                    UPDATE insurance_products SET {', '.join(f'{c} = ?' for c in values)}, updated_at = datetime('now')
                    WHERE id = ?
                    """,
                    (*values.values(), existing_id),
                )
                stats["updated"] += 1

        for product_db_id, infos in merged_into.items():
            raw_meta, status = existing_meta[product_db_id]
            meta = json.loads(raw_meta or "{}")
            meta["tii"] = infos
            new_status = status
            if status == "unknown":
                new_status = "active" if any(not i["sale_end_date"] for i in infos) else "discontinued"
            stats["existing_products_enriched"] += 1
            if not dry_run:
                conn.execute(
                    "UPDATE insurance_products SET metadata = ?, status = ?, updated_at = datetime('now') WHERE id = ?",
                    (json.dumps(meta, ensure_ascii=False), new_status, product_db_id),
                )

        if recategorize_ib:
            for row in conn.execute(
                "SELECT id, product_name FROM insurance_products WHERE source = 'ib_disclosure' AND category = 'property'"
            ).fetchall():
                stats["ib_recategorized"] += 1
                if not dry_run:
                    conn.execute(
                        "UPDATE insurance_products SET category = ? WHERE id = ?",
                        (infer_category(row[1], "property"), row[0]),
                    )
            # IB rows were stored under the full legal name; use the short
            # name like every other source (the bridge script now does too).
            for full_name, short_name, company_id in conn.execute(
                "SELECT name, short_name, id FROM insurance_companies WHERE name <> short_name"
            ).fetchall():
                count = conn.execute(
                    "SELECT COUNT(*) FROM insurance_products WHERE source = 'ib_disclosure' AND company_name = ?",
                    (full_name,),
                ).fetchone()[0]
                if count:
                    stats["ib_company_renamed"] += count
                    if not dry_run:
                        conn.execute(
                            "UPDATE insurance_products SET company_name = ?, company_id = ? "
                            "WHERE source = 'ib_disclosure' AND company_name = ?",
                            (short_name, company_id, full_name),
                        )

    return {"tii_records": len(records), "companies_added": companies_added, **dict(stats), "dry_run": dry_run}


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--recategorize-ib", action="store_true")
    args = parser.parse_args()
    print(json.dumps(run(args.dry_run, args.recategorize_ib), ensure_ascii=False, indent=2))


if __name__ == "__main__":
    main()
