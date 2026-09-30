"""Phase 2.5: ingest TII's public ResultQueryAll.aspx full-index list pages.

`ResultQueryAll.aspx?page=N` is a public, non-CAPTCHA-gated paginated index
of every product in TII's database -- confirmed live (2026-09-13): page=1
returns 195,255 total records with no query beyond `page`, no auth, no
CAPTCHA. This is a DIFFERENT page from `Query.aspx` (the CAPTCHA-gated
search form -- still completely off-limits, never touched here) and from
`DetailList.aspx` (per-product detail; not fetched by this script -- see
scripts/ingest_tii_product.py for that, still human-in-the-loop only).

What this script does and does not do
----------------------------------------
- Fetches ONLY `ResultQueryAll.aspx?page=N` for N in a caller-given range.
  Nothing else. No query form submission, no CAPTCHA handling, no
  `productId` enumeration or guessing (`DetailList.aspx?productId=...` links
  are only ever read off a page we already fetched, never constructed).
- Rate-limited and resumable by design: a fixed delay between page fetches
  (--delay-seconds), and a small sidecar state file tracks the last
  successfully processed page so --resume can pick back up.
- Stops immediately on HTTP 403 or 429 -- that's the site telling us to
  back off, not a page-not-found -- and records that in the summary as
  rate_limited so a caller doesn't retry blindly in a loop.
- Every record's company_name comes out "" (see list_parser.py's module
  docstring for why) -- reconcile_source_records.py currently skips any
  record with an empty company_name, so these records sit in
  source_product_records/document_registry as raw evidence but will not
  produce a product_families/product_versions row until company_name is
  filled in from somewhere else (a DetailList.aspx fetch, or a company-site
  adapter).

Usage:
    python scripts/ingest_tii_result_pages.py --start-page 1 --end-page 5
    python scripts/ingest_tii_result_pages.py --start-page 6 --end-page 50 --resume
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
TII_DIR = ROOT / "scripts" / "sources" / "tii"
if str(TII_DIR) not in sys.path:
    sys.path.insert(0, str(TII_DIR))

from client import TII_ORIGIN, TiiClient  # noqa: E402
from list_parser import parse_result_page  # noqa: E402

DEFAULT_OUTPUT = ROOT / "backend" / "data" / "tii_result_records.jsonl"
DEFAULT_SNAPSHOT_DIR = ROOT / "backend" / "data" / "tii_result_snapshots"


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
    # Retry: a long unattended crawl died once (2026-09-19, page 2862) on a
    # transient Windows `OSError: [Errno 22]` while writing this tiny file
    # (something briefly held it -- antivirus/indexer). The state file is
    # only a resume marker, so failing to write it once must not kill hours
    # of crawling.
    import time

    payload = json.dumps(state, ensure_ascii=False, indent=2)
    for attempt in range(5):
        try:
            _state_path(output).write_text(payload, encoding="utf-8")
            return
        except OSError:
            if attempt == 4:
                raise
            time.sleep(1 + attempt)


def _append_records(records: list[dict[str, Any]], output: Path) -> None:
    if not records:
        return
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def run(args: argparse.Namespace) -> dict[str, Any]:
    start_page = args.start_page
    if args.resume:
        state = _load_state(args.output)
        last_completed = state.get("last_completed_page")
        if isinstance(last_completed, int) and last_completed >= start_page:
            start_page = last_completed + 1

    pages_requested = max(0, args.end_page - start_page + 1)
    pages_fetched = 0
    records_seen = 0
    total_records_reported: int | None = None
    errors: list[dict[str, Any]] = []
    rate_limited = False
    stopped_at_page: int | None = None

    async with TiiClient(
        snapshot_dir=args.snapshot_dir,
        min_interval_seconds=args.delay_seconds,
        timeout=args.timeout,
        verify=not args.insecure,
    ) as client:
        page = start_page
        while page <= args.end_page:
            url = f"{TII_ORIGIN}/ResultQueryAll.aspx?page={page}"
            try:
                result = await client.fetch(url)
            except httpx.HTTPStatusError as exc:
                status = exc.response.status_code
                if status in (403, 429):
                    rate_limited = True
                    stopped_at_page = page
                    errors.append({"page": page, "error": f"HTTP {status} -- stopping (rate limited)"})
                    break
                errors.append({"page": page, "error": f"HTTP {status}"})
                page += 1
                continue
            except httpx.TransportError as exc:
                errors.append({"page": page, "error": str(exc)[:240]})
                page += 1
                continue

            html = result.content.decode("utf-8", errors="replace")
            try:
                parsed = parse_result_page(html, url)
            except Exception as exc:  # noqa: BLE001 -- one bad page shouldn't abort the whole range
                errors.append({"page": page, "error": f"parse failed: {exc}"})
                page += 1
                continue

            if parsed["total_records"] is not None:
                total_records_reported = parsed["total_records"]

            _append_records(parsed["records"], args.output)
            records_seen += len(parsed["records"])
            pages_fetched += 1

            _save_state(
                args.output,
                {"last_completed_page": page, "rate_limited": False, "total_records_reported": total_records_reported},
            )
            page += 1

    if rate_limited:
        _save_state(
            args.output,
            {
                "last_completed_page": stopped_at_page - 1 if stopped_at_page else None,
                "rate_limited": True,
                "total_records_reported": total_records_reported,
            },
        )

    return {
        "start_page": start_page,
        "end_page": args.end_page,
        "pages_requested": pages_requested,
        "pages_fetched": pages_fetched,
        "records_seen": records_seen,
        "total_records_reported": total_records_reported,
        "rate_limited": rate_limited,
        "stopped_at_page": stopped_at_page,
        "errors": errors,
        "output": str(args.output),
    }


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--start-page", type=int, required=True)
    parser.add_argument("--end-page", type=int, required=True)
    parser.add_argument("--delay-seconds", type=float, default=2.0)
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument(
        "--resume",
        action="store_true",
        help="Skip pages already recorded as completed in <output>.state.json, "
        "starting from the page after the last one that succeeded.",
    )
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Only use if this specific, known host's "
        "certificate genuinely fails to verify -- not as a default.",
    )
    args = parser.parse_args()

    if args.end_page < args.start_page:
        raise SystemExit("--end-page must be >= --start-page")

    summary = asyncio.run(run(args))
    print(json.dumps(summary, ensure_ascii=False, indent=2))
    if summary["rate_limited"]:
        print(
            f"\nStopped at page {summary['stopped_at_page']} due to HTTP 403/429 (rate limited). "
            "Wait before retrying; re-run with --resume once ready.",
            file=sys.stderr,
        )
    if summary["errors"] and not summary["rate_limited"]:
        sys.exit(1)


if __name__ == "__main__":
    main()
