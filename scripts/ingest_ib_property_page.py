"""Phase 2.7: fetch and parse one IB (保險業公開資訊觀測站) product page.

First-version scope, deliberately narrow: given exactly one URL, fetch it
once (a plain GET, no session/cookie tricks) and parse whatever HTML comes
back. No crawling, no following pagination, no submitting IB's product
search form (a plain ASP.NET postback -- not CAPTCHA-gated, but out of
scope for this phase regardless; see
scripts/sources/ib_disclosure/property_parser.py's module docstring for
why and what that means for a bare company-level URL).

Output is SourceProductRecord-shaped JSONL (source="ib_disclosure"),
appended to a staging file -- nothing is written to the inventory database
yet. That's scripts/import_source_records.py + reconcile_source_records.py's
job, same pipeline as the TII side.

Usage:
    python scripts/ingest_ib_property_page.py \\
        --url "https://ins-info.ib.gov.tw/customer/Property_Layout.aspx?UID=03557115"

    # Or parse an already-saved page (no network at all):
    python scripts/ingest_ib_property_page.py --html-file path/to/saved.html
"""

from __future__ import annotations

import argparse
import asyncio
import hashlib
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import httpx

ROOT = Path(__file__).resolve().parent.parent
IB_DIR = ROOT / "scripts" / "sources" / "ib_disclosure"
SCRIPTS_DIR = ROOT / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))
if str(IB_DIR) not in sys.path:
    sys.path.insert(0, str(IB_DIR))

from inventory_http import DEFAULT_HEADERS, referer_for_url  # noqa: E402
from property_parser import parse_property_page  # noqa: E402

DEFAULT_OUTPUT = ROOT / "backend" / "data" / "ib_source_records.jsonl"
DEFAULT_SNAPSHOT_DIR = ROOT / "backend" / "data" / "ib_snapshots"


def _save_snapshot(content: bytes, snapshot_dir: Path) -> str:
    snapshot_dir.mkdir(parents=True, exist_ok=True)
    checksum = hashlib.sha256(content).hexdigest()
    stamp = datetime.now(timezone.utc).strftime("%Y%m%dT%H%M%SZ")
    path = snapshot_dir / f"{stamp}_{checksum[:16]}.html"
    path.write_bytes(content)
    try:
        return str(path.relative_to(ROOT)).replace("\\", "/")
    except ValueError:
        return str(path)


async def fetch_url(url: str, timeout: float, verify: bool) -> tuple[bytes, str]:
    async with httpx.AsyncClient(timeout=timeout, follow_redirects=True, headers=DEFAULT_HEADERS, verify=verify) as client:
        response = await client.get(url, headers={"Referer": referer_for_url(url)})
        response.raise_for_status()
        return response.content, str(response.url)


def append_records(records: list[dict[str, Any]], output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        for record in records:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def run(args: argparse.Namespace) -> None:
    if args.html_file:
        html = args.html_file.read_text(encoding="utf-8")
        page_url = args.url or f"file://{args.html_file.resolve()}"
        try:
            snapshot_path = str(args.html_file.resolve().relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            snapshot_path = str(args.html_file)
    else:
        if not args.url:
            raise SystemExit("pass --url (or --html-file for a locally saved page)")
        content, final_url = await fetch_url(args.url, args.timeout, verify=not args.insecure)
        snapshot_path = _save_snapshot(content, args.snapshot_dir)
        html = content.decode("utf-8", errors="replace")
        page_url = final_url

    records = parse_property_page(html, page_url=page_url, source_html_path=snapshot_path)
    payloads = [r.to_dict() for r in records]
    append_records(payloads, args.output)

    print(json.dumps(payloads, ensure_ascii=False, indent=2))
    print(f"\n{len(payloads)} record(s) appended to {args.output}", file=sys.stderr)

    for payload in payloads:
        if not payload.get("product_code") and not payload.get("product_name"):
            reason = payload.get("raw_fields", {}).get("note") or "no product row was found on this page"
            print(
                f"NOTE: record for source_product_id={payload['source_product_id']!r} has no "
                f"product_code/product_name -- {reason}",
                file=sys.stderr,
            )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--url", help="An IB disclosure page URL to fetch directly")
    parser.add_argument(
        "--html-file",
        type=Path,
        help="Parse an already-saved HTML file instead of fetching --url. If --url is also "
        "given, it's used only to resolve relative links/UID -- nothing is fetched.",
    )
    parser.add_argument("--timeout", type=float, default=20.0)
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    parser.add_argument("--snapshot-dir", type=Path, default=DEFAULT_SNAPSHOT_DIR)
    parser.add_argument(
        "--insecure",
        action="store_true",
        help="Disable TLS certificate verification. Only use if this specific, known host's "
        "certificate genuinely fails to verify -- not as a default.",
    )
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
