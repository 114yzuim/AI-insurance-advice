"""Fill company_name on TII full-index records (see
scripts/sources/tii/company_resolver.py for the rules) and write a report.

Input is the raw crawl output of scripts/ingest_tii_result_pages.py, which
contains duplicate rows (TII's paging order is unstable, so the same
product shows up on several pages). Output is deduplicated by
source_product_id -- the rows are content-identical, last one wins.

Nothing is written to any database; this only produces:
  <output>                 resolved JSONL (company_name / company_type filled,
                           raw_fields["company_resolution"] records how)
  <output>.report.json     counts per company / method + samples to eyeball

Usage:
    python scripts/resolve_tii_companies.py \
        --input C:/Users/rabbi/tii_crawl/tii_full.jsonl \
        --output C:/Users/rabbi/tii_crawl/tii_resolved.jsonl
"""

from __future__ import annotations

import argparse
import json
import random
import sys
from collections import Counter, defaultdict
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "scripts" / "sources" / "tii"))

from company_resolver import resolve_company  # noqa: E402


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--input", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--samples", type=int, default=15, help="Samples per method in the report.")
    args = parser.parse_args()

    records: dict[str, dict] = {}
    raw_lines = 0
    with args.input.open(encoding="utf-8") as f:
        for line in f:
            if not line.strip():
                continue
            raw_lines += 1
            record = json.loads(line)
            records[record["source_product_id"]] = record

    by_method: Counter = Counter()
    by_company: Counter = Counter()
    by_type: Counter = Counter()
    literal_by_company: dict[str, Counter] = defaultdict(Counter)
    samples: dict[str, list] = defaultdict(list)

    with args.output.open("w", encoding="utf-8") as out:
        for record in records.values():
            match = resolve_company(record["product_name"])
            record["company_name"] = match.company_name
            record["company_type"] = match.company_type
            record.setdefault("raw_fields", {})["company_resolution"] = {"method": match.method, "matched": match.matched}
            out.write(json.dumps(record, ensure_ascii=False) + "\n")

            by_method[match.method] += 1
            by_company[match.company_name or "(未知)"] += 1
            by_type[match.company_type or "(未知)"] += 1
            literal_by_company[match.company_name or "(未知)"][match.matched] += 1
            samples[match.method].append({"product_name": record["product_name"], "company": match.company_name, "matched": match.matched})

    rng = random.Random(0)
    report = {
        "raw_lines": raw_lines,
        "unique_products": len(records),
        "resolved": len(records) - by_method["unknown"],
        "unknown": by_method["unknown"],
        "by_method": dict(by_method.most_common()),
        "by_type": dict(by_type.most_common()),
        "by_company": dict(by_company.most_common()),
        "matched_literals_by_company": {c: dict(v.most_common()) for c, v in literal_by_company.items()},
        "samples": {m: rng.sample(s, min(args.samples, len(s))) for m, s in samples.items()},
    }
    report_path = args.output.with_name(args.output.name + ".report.json")
    report_path.write_text(json.dumps(report, ensure_ascii=False, indent=2), encoding="utf-8")
    print(json.dumps({k: report[k] for k in ("raw_lines", "unique_products", "resolved", "unknown", "by_method", "by_type")}, ensure_ascii=False, indent=2))
    print(f"report: {report_path}")


if __name__ == "__main__":
    main()
