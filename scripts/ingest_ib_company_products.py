"""Phase 2.8: ingest one or more IB companies' full product lists.

For each company in backend/data/ib_companies_seed.json: GET its query page,
POST the same page's search form with a blank product code and keyword
(query_client.py -- the same "list everything" submission a human clicking
"查詢" with nothing typed would make; not CAPTCHA-gated, not a bypass of
anything -- see scripts/sources/ib_disclosure/README.md), then page through
results via the plain `?Page=N` query string (confirmed live to NOT need a
`__doPostBack`) until `--max-pages` or the last page, whichever comes first.

Output is SourceProductRecord-shaped JSONL (source="ib_disclosure"),
appended to a staging file -- nothing is written to the inventory database
yet (scripts/import_source_records.py + reconcile_source_records.py do
that, same as every other source in this pipeline).

LICENSING NOTE: this is research / internal-verification tooling. IB's own
footer asks that data be attributed, kept intact, and not used commercially
-- confirm actual licensing terms with IB / 金融監督管理委員會保險局 before any
production or commercial use. See scripts/sources/ib_disclosure/README.md.

Usage:
    python scripts/ingest_ib_company_products.py --company-uid 03557115 --max-pages 1
    python scripts/ingest_ib_company_products.py --max-pages 5 --resume
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
IB_DIR = ROOT / "scripts" / "sources" / "ib_disclosure"
if str(IB_DIR) not in sys.path:
    sys.path.insert(0, str(IB_DIR))

from query_client import IbQueryClient  # noqa: E402
from property_parser import parse_property_page  # noqa: E402

DEFAULT_SEED = BACKEND / "data" / "ib_companies_seed.json"
DEFAULT_OUTPUT = BACKEND / "data" / "ib_company_products.jsonl"
DEFAULT_SNAPSHOT_DIR = BACKEND / "data" / "ib_disclosure_snapshots"


def _state_path(output: Path) -> Path:
    return output.with_name(output.name + ".state.json")


def _load_state(output: Path) -> dict[str, Any]:
    path = _state_path(output)
    if not path.exists():
        return {}
    try:
        return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _save_state(output: Path, state: dict[str, Any]) -> None:
    _state_path(output).write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _append_records(records: list[dict[str, Any]], output: Path) -> None:
    if not records:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


def _load_companies(seed_path: Path, company_uid: str | None, limit_companies: int | None) -> list[dict[str, Any]]:
    companies = json.loads(seed_path.read_text(encoding="utf-8"))
    if company_uid:
        companies = [c for c in companies if c.get("company_uid") == company_uid]
    if limit_companies:
        companies = companies[:limit_companies]
    return companies


async def run(args: argparse.Namespace) -> dict[str, Any]:
    companies = _load_companies(args.seed, args.company_uid, args.limit_companies)
    state = _load_state(args.output) if args.resume else {}

    stats: dict[str, Any] = {
        "companies_seen": len(companies),
        "companies_fetched": 0,
        "pages_fetched": 0,
        "records_seen": 0,
        "total_records_by_company": {},
        "rate_limited": False,
        "errors": [],
    }

    async with IbQueryClient(
        snapshot_dir=args.snapshot_dir,
        min_interval_seconds=args.delay_seconds,
        timeout=args.timeout,
        verify=not args.insecure,
    ) as client:
        for company in companies:
            uid = company.get("company_uid", "")
            query_url = company.get("query_url", "")
            if not query_url:
                stats["errors"].append({"company_uid": uid, "error": "no query_url in seed entry"})
                continue

            company_state = state.get(uid, {})
            start_page = company_state.get("last_completed_page", 0) + 1 if args.resume else 1

            try:
                first = await client.query(query_url)
            except httpx.HTTPStatusError as exc:
                if exc.response.status_code in (403, 429):
                    stats["rate_limited"] = True
                    stats["errors"].append({"company_uid": uid, "error": f"HTTP {exc.response.status_code} on initial query -- stopping"})
                    break
                stats["errors"].append({"company_uid": uid, "error": f"HTTP {exc.response.status_code} on initial query"})
                continue
            except httpx.TransportError as exc:
                stats["errors"].append({"company_uid": uid, "error": str(exc)[:240]})
                continue

            stats["companies_fetched"] += 1
            html = first.content.decode("utf-8", errors="replace")
            parsed = parse_property_page(
                html,
                page_url=first.final_url,
                source_html_path=first.snapshot_path,
                insurance_category=company.get("insurance_category"),
            )
            total_pages = parsed[0].raw_fields.get("total_pages", 1) if parsed else 1
            stats["total_records_by_company"][uid] = total_pages

            pages_done_this_run = 0
            if start_page <= 1:
                _append_records([r.to_dict() for r in parsed], args.output)
                stats["records_seen"] += len(parsed)
                stats["pages_fetched"] += 1
                pages_done_this_run += 1
                state[uid] = {"last_completed_page": 1, "total_pages": total_pages}
                _save_state(args.output, state)
                next_page = 2
            else:
                next_page = start_page

            while pages_done_this_run < args.max_pages and next_page <= total_pages:
                try:
                    result = await client.get_page(query_url, next_page)
                except httpx.HTTPStatusError as exc:
                    if exc.response.status_code in (403, 429):
                        stats["rate_limited"] = True
                        stats["errors"].append(
                            {"company_uid": uid, "page": next_page, "error": f"HTTP {exc.response.status_code} -- stopping"}
                        )
                        break
                    stats["errors"].append({"company_uid": uid, "page": next_page, "error": f"HTTP {exc.response.status_code}"})
                    next_page += 1
                    continue
                except httpx.TransportError as exc:
                    stats["errors"].append({"company_uid": uid, "page": next_page, "error": str(exc)[:240]})
                    next_page += 1
                    continue

                page_html = result.content.decode("utf-8", errors="replace")
                page_records = parse_property_page(
                    page_html,
                    page_url=result.final_url,
                    source_html_path=result.snapshot_path,
                    insurance_category=company.get("insurance_category"),
                )
                _append_records([r.to_dict() for r in page_records], args.output)
                stats["records_seen"] += len(page_records)
                stats["pages_fetched"] += 1
                pages_done_this_run += 1
                state[uid] = {"last_completed_page": next_page, "total_pages": total_pages}
                _save_state(args.output, state)
                next_page += 1

            if stats["rate_limited"]:
                break

    return stats


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--seed", type=Path, default=DEFAULT_SEED)
    parser.add_argument("--company-uid", help="Only ingest this one company_uid from the seed file")
    parser.add_argument("--limit-companies", type=int, help="Only process the first N companies in the seed file")
    parser.add_argument("--max-pages", type=int, default=1, help="Max pages to fetch per company in this run")
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Continue each company from the page after its last-completed page in "
        "<output>.state.json, instead of always restarting at page 1.",
    )
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
    elif summary["errors"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
