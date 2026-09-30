"""Phase 2.6: best-effort DetailList.aspx backfill for list-origin TII records.

Background -- read this before changing anything here
--------------------------------------------------------
`scripts/ingest_tii_result_pages.py` (Phase 2.5) populates
source_product_records from the public `ResultQueryAll.aspx` index, which
has no company_name column at all -- every one of those rows has an empty
company_name and is skipped by reconcile_source_records.py. This script
tries to fill that gap by fetching each candidate's own DetailList.aspx URL
(already sitting in source_product_url/detail_url, read off the list page --
never guessed, never enumerated).

**Verified live (2026-09-13): this mostly does not work.** Navigating
straight to `DetailList.aspx?productId=<any real id>` -- cold session, no
prior navigation -- redirects to `Query.aspx` (TII's CAPTCHA-gated search
form), confirmed via the browser's own `window.location.href` after
navigating, tried against two different real product ids taken from a live
`ResultQueryAll.aspx` page. We do not attempt to reverse-engineer whatever
referer/session sequence would satisfy TII's check here -- that would be
probing for a bypass to a deliberate access control, the same category of
thing this project refuses to do to the CAPTCHA itself. See
scripts/sources/tii/README.md for the full writeup.

So this script makes one honest, plain GET per candidate URL (via the same
rate-limited `TiiClient` everything else here uses), and handles the
(expected, common) redirect-to-Query.aspx case explicitly:

  - It is detected by the fetch's *final* URL (after following redirects)
    landing on Query.aspx -- not by guessing at content -- and confirmed
    defensively by a couple of Query.aspx-only text markers, so a
    transient/differently-shaped block page can't slip past undetected.
  - The record is marked `detail_status: "blocked_query_redirect"` in
    raw_payload["detail"] and left otherwise alone: company_name and every
    other column stay exactly as they were. Critically, detail_parser.py's
    generic label:value table scraper is NEVER run on a redirected page --
    Query.aspx's own form contains rows like "銷售日區間：" and "保險類別："
    that would otherwise silently masquerade as real product data through
    detail_parser.py's keyword map (it maps "銷售日" -> sale_start_date and
    "保險類別" -> insurance_type, which would happily eat the search form's
    placeholder/blank values as if they were this product's own fields).

If a candidate's DetailList.aspx *does* load real content -- e.g. some
future session-state change we don't yet understand makes this work again --
detail_parser.py / document_parser.py run exactly as in Phase 1, and the
result is classified `detail_status: "ok"` (recognizable fields were found)
or `"shell_only"` (a real page loaded but nothing in detail_parser.py's
keyword map matched -- see that module's own "unverified" caveat).

Usage:
    python scripts/resolve_tii_details.py --limit 5
    python scripts/resolve_tii_details.py --limit 50 --delay-seconds 3
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
TII_DIR = ROOT / "scripts" / "sources" / "tii"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(TII_DIR) not in sys.path:
    sys.path.insert(0, str(TII_DIR))

from inventory_db import get_inventory_connection  # noqa: E402
import inventory_repository as repo  # noqa: E402
from client import TiiClient  # noqa: E402
from detail_parser import parse_detail_page  # noqa: E402

DEFAULT_SNAPSHOT_DIR = BACKEND / "data" / "tii_detail_snapshots"

# What actually happens on a direct DetailList.aspx hit (verified live,
# 2026-09-13) is NOT a server-side HTTP redirect -- httpx's `final_url` never
# changes, because there isn't one. TII returns a normal 200 response whose
# body is a small <script> block that does the redirect client-side:
#     alert("識別碼錯誤！"); location.href = "Query.aspx";
# A real browser executes that and ends up on Query.aspx (which is what an
# earlier manual check saw via window.location.href); a plain GET like this
# script's does not execute it, so the *only* reliable signal is this exact
# script text in the response body. Checked first and treated as
# authoritative; the "final URL literally is Query.aspx" and generic
# Query.aspx-form-text checks are kept as a defensive fallback in case TII's
# behavior ever changes to a real HTTP redirect or a different block page.
_JS_REDIRECT_MARKER = 'location.href = "Query.aspx"'
_QUERY_FORM_MARKERS = ("查詢識別碼", "圖形驗證碼", "《說明》請輸入保險商品名稱的可能關鍵字")


def _looks_like_query_form(final_url: str, html: str) -> bool:
    if _JS_REDIRECT_MARKER in html:
        return True
    if "query.aspx" in final_url.lower():
        return True
    return any(marker in html for marker in _QUERY_FORM_MARKERS)


def _fetch_candidates(conn, limit: int) -> tuple[int, list[dict[str, Any]]]:
    total = conn.execute(
        """
        SELECT COUNT(*)
        FROM source_product_records spr
        JOIN inventory_sources s ON s.id = spr.source_id
        WHERE s.code = 'tii' AND (spr.company_name IS NULL OR spr.company_name = '')
        """
    ).fetchone()[0]

    rows = conn.execute(
        """
        SELECT spr.id, spr.source_product_id, spr.source_product_url, spr.raw_payload
        FROM source_product_records spr
        JOIN inventory_sources s ON s.id = spr.source_id
        WHERE s.code = 'tii' AND (spr.company_name IS NULL OR spr.company_name = '')
        ORDER BY spr.id
        LIMIT ?
        """,
        (limit,),
    ).fetchall()

    candidates = []
    for row_id, source_product_id, source_product_url, raw_payload_json in rows:
        detail_url = source_product_url or ""
        if not detail_url:
            try:
                raw_payload = json.loads(raw_payload_json) if raw_payload_json else {}
            except json.JSONDecodeError:
                raw_payload = {}
            detail_url = raw_payload.get("detail_url") or raw_payload.get("source_product_url") or ""
        candidates.append(
            {"id": row_id, "source_product_id": source_product_id, "detail_url": detail_url}
        )
    return total, candidates


async def run(args: argparse.Namespace) -> dict[str, Any]:
    stats = {
        "candidates": 0,
        "fetched": 0,
        "detail_ok": 0,
        "shell_only": 0,
        "blocked_query_redirect": 0,
        "parse_failed": 0,
        "documents_seen": 0,
        "records_changed": 0,
        "rate_limited": False,
        "errors": [],
    }

    with get_inventory_connection() as conn:
        repo.ensure_default_sources(conn)
        total, candidates = _fetch_candidates(conn, args.limit)
        stats["candidates"] = total
        if not candidates:
            return stats

        crawl_run_id = repo.create_crawl_run(
            conn, "tii", "refresh", metadata={"script": "resolve_tii_details.py", "limit": args.limit}
        )

        async with TiiClient(
            snapshot_dir=args.snapshot_dir,
            min_interval_seconds=args.delay_seconds,
            timeout=args.timeout,
            verify=not args.insecure,
        ) as client:
            for candidate in candidates:
                url = candidate["detail_url"]
                if not url:
                    stats["errors"].append({"id": candidate["id"], "error": "no detail_url/source_product_url on record"})
                    continue

                try:
                    result = await client.fetch(url)
                except httpx.HTTPStatusError as exc:
                    status = exc.response.status_code
                    if status in (403, 429):
                        stats["rate_limited"] = True
                        stats["errors"].append({"id": candidate["id"], "error": f"HTTP {status} -- stopping (rate limited)"})
                        break
                    stats["parse_failed"] += 1
                    stats["errors"].append({"id": candidate["id"], "error": f"HTTP {status}"})
                    continue
                except httpx.TransportError as exc:
                    stats["parse_failed"] += 1
                    stats["errors"].append({"id": candidate["id"], "error": str(exc)[:240]})
                    continue

                stats["fetched"] += 1
                html = result.content.decode("utf-8", errors="replace")

                if _looks_like_query_form(result.final_url, html):
                    stats["blocked_query_redirect"] += 1
                    parsed_record = {
                        "detail_status": "blocked_query_redirect",
                        "detail_url": url,
                        "final_url": result.final_url,
                        "fetched_at": result.fetched_at,
                        "source_html_path": result.snapshot_path,
                    }
                    if repo.update_source_product_record_from_detail(conn, candidate["id"], parsed_record):
                        stats["records_changed"] += 1
                    continue

                try:
                    record = parse_detail_page(
                        html,
                        detail_url=url,
                        source_product_id=candidate["source_product_id"],
                        source_html_path=result.snapshot_path,
                    )
                except Exception as exc:  # noqa: BLE001 -- one bad page shouldn't abort the whole run
                    stats["parse_failed"] += 1
                    stats["errors"].append({"id": candidate["id"], "error": f"parse failed: {exc}"})
                    continue

                found_something = bool(record.company_name or record.product_name)
                detail_status = "ok" if found_something else "shell_only"
                stats["detail_ok" if found_something else "shell_only"] += 1

                parsed_record = record.to_dict()
                parsed_record["detail_status"] = detail_status
                parsed_record["final_url"] = result.final_url

                if repo.update_source_product_record_from_detail(conn, candidate["id"], parsed_record):
                    stats["records_changed"] += 1

                for doc in record.documents:
                    doc_record = {
                        "url": doc.url,
                        "document_type": doc.document_type.value,
                        "title": doc.label,
                        "source": "tii",
                        "source_document_id": doc.open_id,
                    }
                    repo.upsert_document_registry(conn, candidate["id"], doc_record)
                    stats["documents_seen"] += 1

        repo.finish_crawl_run(
            conn,
            crawl_run_id,
            status="failed" if stats["errors"] and not stats["rate_limited"] else "succeeded",
            records_seen=stats["fetched"],
            records_changed=stats["records_changed"],
            error="; ".join(str(e) for e in stats["errors"][:5]),
        )

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Only use if this specific, known host's "
        "certificate genuinely fails to verify -- not as a default.",
    )
    args = parser.parse_args()

    summary = asyncio.run(run(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["rate_limited"]:
        print("\nStopped early: HTTP 403/429 (rate limited).", file=sys.stderr)


if __name__ == "__main__":
    main()
