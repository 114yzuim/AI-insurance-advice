"""Phase 2.9: backfill IB source_product_records with their 5 detail pages.

For each candidate `source_product_records` row with source='ib_disclosure',
fetch its 5 `property5-1-{1..5}.aspx?UID=<company_uid>&proc=<product_code>`
pages (plain GETs, no CAPTCHA, no postback -- see
scripts/sources/ib_disclosure/detail_parser.py's module docstring), parse
each with detail_parser.py, and merge the results into that same
source_product_records row via
inventory_repository.update_source_product_record_from_detail() (which
already preserves the original list-ingest evidence and only fills
currently-blank columns -- see that function's docstring; nothing IB-specific
needed changing there).

Document handling: every real file reference on these pages is an ASP.NET
LinkButton with no static URL (see document_parser.py) -- `url=""`. Writing
that straight into document_registry would collide: its UNIQUE constraint is
(source_record_id, url), so two such documents on the same product (e.g. a
rate table AND a commission table, both url="") would overwrite each other.
This script gives each a synthesized, obviously-not-a-real-URL placeholder
key instead -- `urn:ib-linkbutton:<company_uid>:<product_code>:<event_target>`
-- deterministic (so re-running is still idempotent) and unambiguous (the
`urn:` scheme is a standard signal "this is an identifier, not a fetchable
location", so nothing downstream could mistake it for a working download
link). The real evidence (visible filename, postback event target) is kept
in the row's metadata either way.

LICENSING NOTE: this is research / internal-verification tooling. IB's own
footer asks that data be attributed, kept intact, and not used commercially
-- confirm actual licensing terms with IB / 金融監督管理委員會保險局 before any
production or commercial use. See scripts/sources/ib_disclosure/README.md.

Usage:
    python scripts/resolve_ib_product_details.py --company-uid 03557115 --limit 1
"""

from __future__ import annotations

import argparse
import asyncio
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
BACKEND = ROOT / "backend"
IB_DIR = ROOT / "scripts" / "sources" / "ib_disclosure"
if str(BACKEND) not in sys.path:
    sys.path.insert(0, str(BACKEND))
if str(ROOT / "scripts") not in sys.path:
    sys.path.insert(0, str(ROOT / "scripts"))
if str(IB_DIR) not in sys.path:
    sys.path.insert(0, str(IB_DIR))

from inventory_db import get_inventory_connection  # noqa: E402
import inventory_repository as repo  # noqa: E402
from query_client import IbQueryClient  # noqa: E402
from detail_parser import parse_detail_page  # noqa: E402
from source import DocumentType  # noqa: E402

# Which function pages carry an "inline_text"/"claim_document_text" field
# when their value cell has real text but no LinkButton -- see
# detail_parser.py's _parse_policy_terms / _parse_short_term_rate_table /
# _parse_claim_info. Function 1 (basic_info) and 4 (fees_and_rebate) never
# produce one of these fields at all, so they're absent here on purpose,
# not an oversight.
_INLINE_TEXT_FUNCTIONS = {
    2: ("inline_text", DocumentType.POLICY_TERMS),
    3: ("inline_text", DocumentType.SHORT_TERM_RATE_TABLE),
    5: ("claim_document_text", DocumentType.CLAIM_DOCUMENT),
}

DEFAULT_SNAPSHOT_DIR = BACKEND / "data" / "ib_disclosure_snapshots"

_FUNCTION_LABELS = {
    1: "basic_info",
    2: "policy_terms",
    3: "short_term_rate_table",
    4: "fees_and_rebate",
    5: "claim_info",
}


def _fetch_candidates(
    conn, company_uid: str | None, only_missing_details: bool, limit: int
) -> tuple[int, list[dict[str, Any]]]:
    # company_uid isn't its own column on source_product_records (it's part
    # of raw_payload, same as the rest of IB's shape-specific fields), so
    # filtering on it happens in Python below rather than in this SQL.
    sql = """
        SELECT spr.id, spr.product_code, spr.raw_payload
        FROM source_product_records spr
        JOIN inventory_sources s ON s.id = spr.source_id
        WHERE s.code = 'ib_disclosure'
        ORDER BY spr.id
    """
    rows = conn.execute(sql).fetchall()

    candidates = []
    for row_id, product_code, raw_payload_json in rows:
        try:
            raw_payload = json.loads(raw_payload_json) if raw_payload_json else {}
        except json.JSONDecodeError:
            raw_payload = {}
        row_uid = raw_payload.get("company_uid") or ""
        if company_uid and row_uid != company_uid:
            continue
        if only_missing_details and isinstance(raw_payload.get("detail"), dict):
            continue
        if not product_code or not row_uid:
            continue
        candidates.append({"id": row_id, "product_code": product_code, "company_uid": row_uid})

    total = len(candidates)
    return total, candidates[:limit]


def _merge_function_results(function_results: dict[int, dict[str, Any]]) -> dict[str, Any]:
    """Combine the 5 per-function parse results into one dict shaped for
    inventory_repository.update_source_product_record_from_detail().

    Uses the exact volatile-field names
    (inventory_repository._VOLATILE_PAYLOAD_KEYS) so re-running this script
    over an unchanged product doesn't register as a content change: a plain
    "fetched_at" here (not "detail_fetched_at") gets stripped by
    stable_payload_for_hash()'s existing top-level-of-"detail" handling, and
    each function's own `source_html_path` is pulled out into one top-level
    "snapshot_paths" list (also volatile-stripped) rather than left buried
    inside `functions.<label>.source_html_path`, which stable_payload_for_hash
    does not descend into (see its docstring -- deliberately not recursive).
    """
    snapshot_paths = [r["source_html_path"] for r in function_results.values() if r.get("source_html_path")]
    merged: dict[str, Any] = {
        "fetched_at": datetime.now(timezone.utc).isoformat(),
        "snapshot_paths": snapshot_paths,
        "functions": {
            _FUNCTION_LABELS[n]: {k: v for k, v in result.items() if k not in ("documents", "source_html_path")}
            for n, result in function_results.items()
        },
    }
    basic = function_results.get(1, {})
    fields = basic.get("fields", {})
    for field_name in ("product_code", "product_name", "insurance_type", "approval_date", "approval_number"):
        if fields.get(field_name):
            merged[field_name] = fields[field_name]
    for field_name in (
        "latest_approval_date",
        "latest_approval_number",
        "last_sent_to_tii_date",
        "last_sent_to_tii_number",
    ):
        if fields.get(field_name):
            merged[field_name] = fields[field_name]
    return merged


# Second line of defense against detail_parser.py's known disclosure-table
# header-row ambiguity (see detail_parser.py's _HEADER_ROW_LABELS comment):
# verified live 2026-09-14 that not every such header uses one of the two
# known header LABELS -- function 3's (短期費率表) header row is
# label="範圍", value="內容", where "範圍" isn't a value distinctive enough
# to blocklist by label alone (a real per-field label could plausibly be
# "範圍" too). Blocklisting by these exact known bogus VALUES instead is
# safe here because they're too short/generic to ever be genuine disclosure
# content (contrast with the real inline texts already seen, which run to
# multiple sentences -- see the module's resolve_ib_product_details docstring
# test evidence).
_KNOWN_HEADER_ARTIFACT_VALUES = {"內容", "揭露內容", "保險契約條款內容"}
_MIN_INLINE_TEXT_CHARS = 6


def _inline_text_entry(
    function_number: int, text: str, company_uid: str, product_code: str
) -> dict[str, Any] | None:
    """One product's function page had real text in a value cell but no
    LinkButton at all (e.g. "本商品不適用短期費率", or a claim-document
    description written directly on the page) -- not a download candidate,
    not a failure, just content that already IS the document. Recorded as
    its own document_registry row, AVAILABLE from the moment it's seen (no
    download step exists for it, see resolve_ib_product_details.py's and
    download_ib_documents.py's module docstrings -- this is a genuinely
    different shape of "document" than the LinkButton ones those handle).
    """
    field_name, document_type = _INLINE_TEXT_FUNCTIONS.get(function_number, (None, None))
    stripped = text.strip()
    if field_name is None or not stripped:
        return None
    if stripped in _KNOWN_HEADER_ARTIFACT_VALUES or len(stripped) < _MIN_INLINE_TEXT_CHARS:
        return None
    return {
        "url": f"urn:ib-inline-text:{company_uid}:{product_code}:{function_number}",
        "document_type": document_type.value,
        "title": "",
        "source": "ib_disclosure",
        "source_document_id": "",
        "availability_status": "INLINE_TEXT_AVAILABLE",
        "metadata": {
            "function_number": function_number,
            "inline_text": text,
            "note": "Page content with no downloadable file -- see resolve_ib_product_details.py's _inline_text_entry.",
        },
    }


def _document_registry_entries(
    function_results: dict[int, dict[str, Any]], company_uid: str, product_code: str
) -> list[dict[str, Any]]:
    entries = []
    for function_number, result in function_results.items():
        field_name, _ = _INLINE_TEXT_FUNCTIONS.get(function_number, (None, None))
        if field_name:
            inline_entry = _inline_text_entry(function_number, result.get(field_name) or "", company_uid, product_code)
            if inline_entry is not None:
                entries.append(inline_entry)
        for doc in result.get("documents", []):
            if doc.url:
                url = doc.url
                metadata = dict(doc.metadata)
            else:
                # See module docstring: a deterministic, obviously-not-a-real-URL
                # placeholder so multiple url="" documents on one product don't
                # collide on document_registry's (source_record_id, url) key.
                # function_number is part of the key -- verified live that IB
                # reuses LinkButton control names (e.g. "LinkButton1") across
                # *different* property5-1-N pages, so the event target alone
                # is not unique for one product; two same-named LinkButtons on
                # two different function pages would otherwise collide and
                # silently overwrite one document with the other.
                url = f"urn:ib-linkbutton:{company_uid}:{product_code}:{function_number}:{doc.source_document_id}"
                metadata = {**doc.metadata, "note": "No static URL -- see resolve_ib_product_details.py module docstring."}
            entries.append(
                {
                    "url": url,
                    "document_type": doc.document_type.value,
                    "title": doc.label,
                    "source": "ib_disclosure",
                    "source_document_id": doc.source_document_id or "",
                    "metadata": {**metadata, "function_number": function_number},
                }
            )
    return entries


async def run(args: argparse.Namespace) -> dict[str, Any]:
    stats = {
        "candidates": 0,
        "fetched_pages": 0,
        "records_changed": 0,
        "documents_seen": 0,
        "documents_changed": 0,
        "rate_limited": False,
        "errors": [],
    }

    with get_inventory_connection() as conn:
        repo.ensure_default_sources(conn)
        total, candidates = _fetch_candidates(conn, args.company_uid, args.only_missing_details, args.limit)
        stats["candidates"] = total
        if not candidates:
            return stats

        crawl_run_id = repo.create_crawl_run(
            conn, "ib_disclosure", "refresh", metadata={"script": "resolve_ib_product_details.py", "limit": args.limit}
        )

        async with IbQueryClient(
            snapshot_dir=args.snapshot_dir,
            min_interval_seconds=args.delay_seconds,
            timeout=args.timeout,
            verify=not args.insecure,
        ) as client:
            rate_limited = False
            for candidate in candidates:
                if rate_limited:
                    break
                company_uid = candidate["company_uid"]
                product_code = candidate["product_code"]
                function_results: dict[int, dict[str, Any]] = {}

                for function_number in range(1, 6):
                    url = (
                        f"https://ins-info.ib.gov.tw/customer/property5-1-{function_number}.aspx"
                        f"?UID={company_uid}&proc={product_code}"
                    )
                    try:
                        result = await client.get(url)
                    except httpx.HTTPStatusError as exc:
                        status = exc.response.status_code
                        if status in (403, 429):
                            stats["rate_limited"] = True
                            rate_limited = True
                            stats["errors"].append(
                                {"id": candidate["id"], "function": function_number, "error": f"HTTP {status} -- stopping"}
                            )
                            break
                        stats["errors"].append({"id": candidate["id"], "function": function_number, "error": f"HTTP {status}"})
                        continue
                    except httpx.TransportError as exc:
                        stats["errors"].append({"id": candidate["id"], "function": function_number, "error": str(exc)[:240]})
                        continue

                    stats["fetched_pages"] += 1
                    html = result.content.decode("utf-8", errors="replace")
                    try:
                        parsed = parse_detail_page(html, function_number, url)
                        parsed["source_html_path"] = result.snapshot_path
                    except Exception as exc:  # noqa: BLE001
                        stats["errors"].append(
                            {"id": candidate["id"], "function": function_number, "error": f"parse failed: {exc}"}
                        )
                        continue
                    function_results[function_number] = parsed

                if rate_limited:
                    break
                if not function_results:
                    continue

                merged_record = _merge_function_results(function_results)
                if repo.update_source_product_record_from_detail(conn, candidate["id"], merged_record):
                    stats["records_changed"] += 1

                for entry in _document_registry_entries(function_results, company_uid, product_code):
                    _, doc_changed = repo.upsert_document_registry(conn, candidate["id"], entry)
                    stats["documents_seen"] += 1
                    if doc_changed:
                        stats["documents_changed"] += 1

        repo.finish_crawl_run(
            conn,
            crawl_run_id,
            status="failed" if stats["errors"] and not stats["rate_limited"] else "succeeded",
            records_seen=stats["fetched_pages"],
            records_changed=stats["records_changed"],
            error="; ".join(str(e) for e in stats["errors"][:5]),
        )

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--limit", type=int, default=20)
    parser.add_argument("--company-uid", help="Only resolve details for this company_uid")
    parser.add_argument(
        "--only-missing-details",
        action="store_true",
        help="Skip records that already have a raw_payload['detail'] section from a prior run",
    )
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
