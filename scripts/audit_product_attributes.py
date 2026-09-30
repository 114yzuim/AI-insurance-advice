"""Grounding audit for product_attributes: does each extracted value
actually appear in the product's own source text?

A free local model can invent plausible-looking values (it once copied the
prompt's example "10萬~500萬元" into a product that states no range). This
checks every string value against the clause / DM text the extractor used
(recorded in product_attributes.source_document_ids):
  - exact:  the value (whitespace/punctuation-normalized) is a substring
  - fuzzy:  >= 60% of its CJK/alnum characters' bigrams occur in the source
  - MISSING: neither -- likely invented, needs a human look
Numbers (issue age) must appear in the text next to 投保年齡 / 歲.

Usage:
    python scripts/audit_product_attributes.py            # all rows
    python scripts/audit_product_attributes.py --ids 1695 374
    python scripts/audit_product_attributes.py --show-missing
"""

from __future__ import annotations

import argparse
import json
import re
import sys
import unicodedata
from collections import Counter
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from inventory_db import get_inventory_connection  # noqa: E402

_KEEP = re.compile(r"[一-鿿0-9A-Za-z]")


def _norm(text: str) -> str:
    return "".join(_KEEP.findall(unicodedata.normalize("NFKC", text or "")))


_CN_DIGIT = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}
_CN_UNIT = {"十": 10, "百": 100, "千": 1000}
_CN_RUN = re.compile(r"[零〇一二兩三四五六七八九十百千]+")
# A number followed by the unit that gives it meaning in a clause.
_NUM_UNIT = re.compile(r"(\d+(?:\.\d+)?)(歲|日|天|%|年|倍|萬|元|次|個月|月|小時)")


def _cn_to_int(run: str) -> int:
    """"十六" -> 16, "九十" -> 90, "一百八十" -> 180, "一一〇" -> 110."""
    if not any(ch in _CN_UNIT for ch in run):
        return int("".join(str(_CN_DIGIT[ch]) for ch in run))
    total, current = 0, 0
    for ch in run:
        if ch in _CN_DIGIT:
            current = _CN_DIGIT[ch]
        else:
            total += (current or 1) * _CN_UNIT[ch]
            current = 0
    return total + current


def _digitize(text: str) -> str:
    """NFKC, drop whitespace, and turn Chinese numerals into digits
    ("十六歲" -> "16歲", "九十日" -> "90日"), so a number the model changed
    ("十歲" for "十六歲") can be compared literally. Applied identically to
    value and source, so incidental conversions ("一般" -> "1般") cancel out."""
    text = re.sub(r"\s+", "", unicodedata.normalize("NFKC", text or "")).replace("％", "%")
    return _CN_RUN.sub(lambda m: str(_cn_to_int(m.group(0))), text)


def numbers_ok(value: str, source_digits: str) -> bool:
    """Every "number + unit" in the value must appear verbatim in the source."""
    return all(f"{n}{u}" in source_digits for n, u in _NUM_UNIT.findall(_digitize(value)))


def grounding(value: str, source_norm: str, source_bigrams: set[str], source_digits: str | None = None) -> str:
    v = _norm(value)
    if not v:
        return "exact"
    if v in source_norm:
        return "exact"
    bigrams = {v[i: i + 2] for i in range(len(v) - 1)} or {v}
    hit = sum(1 for b in bigrams if b in source_bigrams) / len(bigrams)
    if hit < 0.6:
        return "MISSING"
    # A paraphrase is fine; a changed number is not ("十歲" vs source "十六歲"
    # shares almost every bigram but flips the condition).
    if source_digits is not None and not numbers_ok(value, source_digits):
        return "MISSING"
    return "fuzzy"


def _source_text(conn, doc_ids: list[int]) -> str:
    parts = []
    for did in doc_ids:
        rows = conn.execute(
            "SELECT text FROM policy_document_chunks WHERE document_id = ? ORDER BY chunk_index", (did,)
        ).fetchall()
        parts.append("\n".join(r[0] for r in rows) if rows else (
            (conn.execute("SELECT parsed_text FROM policy_documents WHERE id = ?", (did,)).fetchone() or [""])[0] or ""
        ))
    return "\n".join(parts)


def audit_row(attrs: dict, source: str) -> list[tuple[str, str, str]]:
    """Returns [(field, value, verdict)]."""
    source_norm = _norm(source)
    source_bigrams = {source_norm[i: i + 2] for i in range(len(source_norm) - 1)}
    source_digits = _digitize(source)
    out = []

    def check(field: str, value):
        if value in (None, "", []):
            return
        out.append((field, str(value), grounding(str(value), source_norm, source_bigrams, source_digits)))

    for field in ("coverage_period", "sum_insured_range"):
        check(field, attrs.get(field))
    for term in attrs.get("payment_terms") or []:
        check("payment_terms", term)
    for benefit in attrs.get("benefits") or []:
        check("benefits.name", benefit.get("name"))
    for item in attrs.get("limits") or []:
        check("limits", item)
    for item in attrs.get("exclusions") or []:
        check("exclusions", item)
    age = attrs.get("issue_age") or {}
    for bound in ("min", "max"):
        n = age.get(bound)
        if n is None:
            continue
        # The number must sit near an issue-age phrase, not anywhere (e.g.
        # "十五足歲" in a death-benefit clause is not an issue age).
        # Only "投保年齡 ... N歲": a table headed 投保年齡 has bare numbers, and
        # an illustration ("50歲的富先生投保…") is not an age limit.
        near = re.search(rf"投保年齡[^。]{{0,40}}?(?<!\d){n}\s*(?:足)?歲", source)
        out.append((f"issue_age.{bound}", str(n), "exact" if near else "MISSING"))
    return out


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--ids", type=int, nargs="*")
    parser.add_argument("--show-missing", action="store_true")
    parser.add_argument(
        "--apply",
        action="store_true",
        help="Remove values that fail the checks from the stored rows (re-validates rows extracted "
        "before a rule was added; rule-derived issue ages are kept).",
    )
    args = parser.parse_args()

    if args.apply:
        from extract_product_attributes import drop_ungrounded, normalize_fields

    with get_inventory_connection() as conn:
        sql = """
            SELECT a.product_db_id, p.product_name, a.attributes, a.source_document_ids, a.field_methods
            FROM product_attributes a JOIN insurance_products p ON p.id = a.product_db_id
        """
        params: list = []
        if args.ids:
            sql += f" WHERE a.product_db_id IN ({', '.join('?' for _ in args.ids)})"
            params = args.ids
        rows = conn.execute(sql + " ORDER BY a.product_db_id", params).fetchall()

        totals: Counter = Counter()
        by_field: dict[str, Counter] = {}
        applied_rows = applied_values = 0
        for pid, name, attrs_json, doc_ids_json, methods_json in rows:
            source = _source_text(conn, json.loads(doc_ids_json))
            attrs, methods = json.loads(attrs_json), json.loads(methods_json)
            # A rule-derived age ("投保年齡 0~75歲") is its own evidence.
            rule_age = attrs.pop("issue_age", None) if methods.get("issue_age") == "rule" else None
            for field, value, verdict in audit_row(attrs, source):
                totals[verdict] += 1
                by_field.setdefault(field.split(".")[0] if "." not in field or field.startswith("issue") else field,
                                    Counter())[verdict] += 1
                if args.show_missing and verdict == "MISSING":
                    print(f"  MISSING  #{pid} {name[:24]} | {field}: {value[:120]}")
            if args.apply:
                dropped = drop_ungrounded(attrs, source) + normalize_fields(attrs)
                if dropped:
                    applied_rows += 1
                    applied_values += len(dropped)
                    methods["_dropped_ungrounded"] = (methods.get("_dropped_ungrounded") or []) + dropped
            if rule_age is not None or "issue_age" not in attrs:
                attrs["issue_age"] = rule_age if rule_age is not None else attrs.get("issue_age")
            if args.apply and methods.get("_dropped_ungrounded") != json.loads(methods_json).get("_dropped_ungrounded"):
                conn.execute(
                    "UPDATE product_attributes SET attributes = ?, field_methods = ? WHERE product_db_id = ?",
                    (json.dumps(attrs, ensure_ascii=False), json.dumps(methods, ensure_ascii=False), pid),
                )

    report = {"products": len(rows), "values": dict(totals),
              "by_field": {k: dict(v) for k, v in sorted(by_field.items())}}
    if args.apply:
        report["applied"] = {"rows_changed": applied_rows, "values_removed": applied_values}
    print(json.dumps(report, ensure_ascii=False, indent=1))


if __name__ == "__main__":
    main()
