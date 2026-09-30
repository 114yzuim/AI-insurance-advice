"""Turn one human-obtained TII product detail page into a SourceProductRecord.

This is the Phase-1 entry point described in the TII source-layer plan. It
does not search TII for you -- see scripts/sources/tii/client.py's module
docstring for why (the query form is CAPTCHA-gated on every request). You
give it either:

  --html-file   an HTML file you already saved from your own browser
                (solve the CAPTCHA, open the product, Ctrl+S / "Save Page"),
  --url         a detail page URL you already navigated to, which this
                script will fetch once (optionally with --cookie-file, a
                text file holding the Cookie header copied from your
                browser devtools, if TII ties the page to your session).

Either way, output is one JSON record appended to a JSONL staging file --
nothing is written to the inventory database yet. That wiring belongs to
Phase 2's reconciliation step once product_versions exists.

Examples
--------
Parse an already-saved page (no network at all):
    python scripts/ingest_tii_product.py \\
        --html-file backend/data/tii_snapshots/manual_2026-09-12.html \\
        --product-id 123456 \\
        --detail-url "https://insprod.tii.org.tw/DetailList.aspx?productId=123456"

Fetch and parse in one step:
    python scripts/ingest_tii_product.py \\
        --url "https://insprod.tii.org.tw/DetailList.aspx?productId=123456" \\
        --product-id 123456 \\
        --cookie-file /path/to/cookie.txt
"""

from __future__ import annotations

import argparse
import asyncio
import json
import re
import sys
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
TII_DIR = ROOT / "scripts" / "sources" / "tii"
if str(TII_DIR) not in sys.path:
    sys.path.insert(0, str(TII_DIR))

from client import TiiClient  # noqa: E402
from detail_parser import parse_detail_page  # noqa: E402

DEFAULT_OUTPUT = ROOT / "backend" / "data" / "tii_source_records.jsonl"

PRODUCT_ID_RE = re.compile(r"[?&]productId=([^&#]+)", re.I)


def guess_product_id(detail_url: str) -> str | None:
    match = PRODUCT_ID_RE.search(detail_url)
    return match.group(1) if match else None


def append_record(record: dict, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    with output.open("a", encoding="utf-8") as f:
        f.write(json.dumps(record, ensure_ascii=False) + "\n")


async def run(args: argparse.Namespace) -> None:
    source_html_path: str | None = None

    if args.html_file:
        html = args.html_file.read_text(encoding="utf-8")
        detail_url = args.detail_url or ""
        if not detail_url:
            raise SystemExit("--detail-url is required when parsing from --html-file "
                              "(needed to resolve relative attachment links)")
        try:
            source_html_path = str(args.html_file.resolve().relative_to(ROOT)).replace("\\", "/")
        except ValueError:
            source_html_path = str(args.html_file)
    elif args.url:
        detail_url = args.url
        cookie_header = args.cookie
        if args.cookie_file:
            cookie_header = args.cookie_file.read_text(encoding="utf-8").strip()
        async with TiiClient(cookie_header=cookie_header) as client:
            result = await client.fetch(detail_url)
        html = result.content.decode("utf-8", errors="replace")
        source_html_path = result.snapshot_path
    else:
        raise SystemExit("pass either --html-file or --url")

    product_id = args.product_id or guess_product_id(detail_url)
    if not product_id:
        raise SystemExit("--product-id is required (couldn't guess it from the URL)")

    record = parse_detail_page(
        html,
        detail_url=detail_url,
        source_product_id=product_id,
        source_html_path=source_html_path,
    )
    payload = record.to_dict()
    append_record(payload, args.output)
    print(json.dumps(payload, ensure_ascii=False, indent=2))
    print(f"\nappended to {args.output}", file=sys.stderr)
    if not record.company_name and not record.product_name:
        print(
            "WARNING: no known fields were recognized on this page -- "
            "the label keyword map in detail_parser.py likely needs updating "
            "for TII's real markup. Check raw_fields above.",
            file=sys.stderr,
        )


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--html-file", type=Path, help="Path to a locally saved detail-page HTML file")
    parser.add_argument("--url", help="A TII detail page URL to fetch directly")
    parser.add_argument("--detail-url", help="Detail page URL (required with --html-file)")
    parser.add_argument("--product-id", help="TII product id (guessed from the URL's productId= if omitted)")
    parser.add_argument(
        "--cookie-file",
        type=Path,
        help="Path to a text file containing the Cookie header to send when using --url "
        "(recommended over --cookie -- a value on the command line lands in your shell "
        "history and is visible to other processes via `ps`)",
    )
    parser.add_argument(
        "--cookie",
        help="Cookie header to send when using --url, copied from your browser. "
        "Prefer --cookie-file: this ends up in shell history and process listings.",
    )
    parser.add_argument("--output", type=Path, default=DEFAULT_OUTPUT)
    args = parser.parse_args()
    asyncio.run(run(args))


if __name__ == "__main__":
    main()
