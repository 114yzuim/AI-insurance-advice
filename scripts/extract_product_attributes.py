"""Extract structured product facts from each product's own clause text --
free, on the operator's PC: regex rules first, then a local Ollama model
(default qwen2.5:7b) for what rules can't read. No paid API.

Input: products that have a parsed clause document (policy_documents with
document_type terms / POLICY_TERMS and text_status='parsed'). Clause text is
rebuilt from policy_document_chunks (company-crawl documents keep no
parsed_text). If the product also has a parsed DM / brochure, its opening is
added -- issue age, payment terms and sum-insured ranges usually live there
(or in 投保規則), not in the clauses.

Output: product_attributes (migration 0008), one row per product:
    attributes = {
      "is_rider": bool,                     # 主約 false / 附約 true
      "coverage_types": [..],               # subset of COVERAGE_TYPES
      "currency": "TWD" | "USD" | ...,
      "coverage_period": str,               # 終身 / 定期20年 / 一年期 ...
      "payment_terms": [str],               # 躉繳 / 6年期 / 20年期 ...
      "issue_age": {"min": int, "max": int},
      "sum_insured_range": str,
      "waiting_periods": [{"target": str, "days": int}],
      "benefits": [{"name": str, "description": str}],
      "limits": [str],                      # 上限 / 自負額 / 次數
      "exclusions": [str],
    }
    field_methods = {field: "rule" | "llm" | "name"}
Fields the text doesn't state are null / [] -- the prompt forbids guessing.

Idempotent: a product is skipped when its source text hash and extractor
version are unchanged.

LLM backend: with QWEN_BASE_URL set (backend/.env), the operator's own Qwen
gateway is called (Ollama-native /api/chat, QWEN_API_KEY as
Bearer token, QWEN_MODEL as the model); otherwise local Ollama. Only this
script uses these settings -- the production site's AI features keep their
own CLAUDE_API_KEY configuration.

Usage:
    python scripts/extract_product_attributes.py --limit 20            # pilot
    python scripts/extract_product_attributes.py --product-db-id 123
    python scripts/extract_product_attributes.py --model qwen2.5:7b
"""

from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import sys
import time
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / "backend"))

from inventory_db import get_inventory_connection  # noqa: E402

EXTRACTOR_VERSION = "v6"
OLLAMA_URL = "http://localhost:11434/api/generate"
COVERAGE_TYPES = ["life", "cancer", "critical", "accident", "daily", "medical", "ltc"]
TERMS_TYPES = ("terms", "POLICY_TERMS")
DM_TYPES = ("dm", "brochure")
MAX_PROMPT_CHARS = 9000  # overridden by --max-chars (e.g. ~4500 for 8k-context models)
NUM_CTX = 16384  # overridden by --num-ctx
# Hard cap on generated tokens: a model that loses the thread under JSON mode
# can otherwise emit whitespace/repeats until the gateway times out (~300 s).
NUM_PREDICT = 2048

# ---------------------------------------------------------------- rules

_CN_DIGITS = {"零": 0, "〇": 0, "一": 1, "二": 2, "兩": 2, "三": 3, "四": 4, "五": 5, "六": 6, "七": 7, "八": 8, "九": 9}


def cn_number(text: str) -> int | None:
    """"三十" -> 30, "九十" -> 90, "一百八十" -> 180, "30" -> 30."""
    text = text.strip()
    if text.isdigit():
        return int(text)
    total, current = 0, 0
    for ch in text:
        if ch in _CN_DIGITS:
            current = _CN_DIGITS[ch]
        elif ch == "十":
            total += (current or 1) * 10
            current = 0
        elif ch == "百":
            total += (current or 1) * 100
            current = 0
        else:
            return None
    return total + current if (total or current) else None


_WAITING_RE = re.compile(
    r"(?:「?([^「」，。、（）()\s]{1,12})」?)?等待期間?(?:為|是)?\s*([零〇一二兩三四五六七八九十百\d]+)\s*[日天]"
)
_CURRENCIES = [("美元", "USD"), ("澳幣", "AUD"), ("人民幣", "CNY"), ("歐元", "EUR"), ("日圓", "JPY"),
               ("新臺幣", "TWD"), ("新台幣", "TWD")]


def rule_waiting_periods(text: str) -> list[dict]:
    found, seen = [], set()
    for target, number in _WAITING_RE.findall(text):
        days = cn_number(number)
        if days is None or days > 3650:
            continue
        key = (target, days)
        if key not in seen:
            seen.add(key)
            found.append({"target": target or "", "days": days})
    return found


def rule_currency(product_name: str, text: str) -> str | None:
    for word, code in _CURRENCIES:
        if word in product_name:
            return code
    if "外幣" in product_name:
        return None  # foreign-currency product; which currency is for the text/LLM
    counts = {code: text.count(word) for word, code in _CURRENCIES}
    best = max(counts, key=counts.get)
    return best if counts[best] else None


_ISSUE_AGE_RE = re.compile(
    r"投保年齡[^。\n]{0,15}?(\d{1,3})\s*(?:足)?(?:歲)?\s*(?:[~～至\-－到]|起至)\s*(\d{1,3})\s*(?:足)?歲"
)


def rule_issue_age(text: str) -> dict | None:
    """"投保年齡 0~75歲" / "投保年齡：15歲至65歲" -> {"min": 0, "max": 75}.
    First plausible range wins."""
    for lo, hi in _ISSUE_AGE_RE.findall(text):
        lo_i, hi_i = int(lo), int(hi)
        if 0 <= lo_i <= hi_i <= 110:
            return {"min": lo_i, "max": hi_i}
    return None


def rule_is_rider(product_name: str) -> bool:
    return bool(re.search(r"附約|附加條款|附加保險|批註條款|附加", product_name))


# ------------------------------------------------------- text selection

_ARTICLE_RE = re.compile(r"第\s*[一二三四五六七八九十百零\d]+\s*條\s*[【\[]([^】\]]{1,30})[】\]]")
_KEEP_TITLES = ("保險範圍", "保險期間", "保險金", "給付", "除外", "不保", "責任", "等待", "限額", "自負",
                "理賠", "承保", "補償", "費用")
_DROP_TITLES = ("名詞定義", "契約撤銷", "告知義務", "寬限期", "效力停止", "恢復", "終止", "受益人", "管轄",
                "時效", "住所", "借款", "減額", "展期", "紅利", "批註", "契約內容")


def select_sections(text: str) -> str:
    """Keep the benefit / exclusion / period articles (and the 附表 tables),
    drop boilerplate (撤銷權, 告知義務, 管轄法院 ...). Falls back to the
    head of the document when it has no 第X條【title】 structure."""
    matches = list(_ARTICLE_RE.finditer(text))
    if len(matches) < 3:
        return text[:MAX_PROMPT_CHARS]
    parts = []
    for i, m in enumerate(matches):
        title = m.group(1)
        body = text[m.start(): matches[i + 1].start() if i + 1 < len(matches) else len(text)]
        if any(k in title for k in _DROP_TITLES):
            continue
        if any(k in title for k in _KEEP_TITLES):
            # 除外 first: it's the article most often cut by the length cap.
            parts.append((0 if ("除外" in title or "不保" in title) else 1, body.strip()))
    tail = text.find("附表")
    if tail >= 0:
        parts.append((2, text[tail: tail + 1500]))
    selected = ""
    for _, body in sorted(parts, key=lambda p: p[0]):
        if len(selected) + len(body) > MAX_PROMPT_CHARS:
            body = body[: max(0, MAX_PROMPT_CHARS - len(selected))]
        selected += body + "\n"
        if len(selected) >= MAX_PROMPT_CHARS:
            break
    return selected or text[:MAX_PROMPT_CHARS]


# ------------------------------------------------------------------ LLM

_SCHEMA = {
    "type": "object",
    "properties": {
        "coverage_types": {"type": "array", "items": {"type": "string", "enum": COVERAGE_TYPES}},
        "currency": {"type": ["string", "null"]},
        "coverage_period": {"type": ["string", "null"]},
        "payment_terms": {"type": "array", "items": {"type": "string"}, "maxItems": 10},
        "issue_age_min": {"type": ["integer", "null"]},
        "issue_age_max": {"type": ["integer", "null"]},
        "sum_insured_range": {"type": ["string", "null"]},
        # maxItems bounds the grammar: a 7B model sometimes loops on one
        # sentence until the token cap and never closes the JSON.
        "benefits": {
            "type": "array",
            "maxItems": 25,
            "items": {"type": "object", "properties": {"name": {"type": "string"}, "description": {"type": "string"}},
                      "required": ["name", "description"]},
        },
        "limits": {"type": "array", "items": {"type": "string"}, "maxItems": 15},
        "exclusions": {"type": "array", "items": {"type": "string"}, "maxItems": 25},
    },
    "required": ["coverage_types", "currency", "coverage_period", "payment_terms", "issue_age_min",
                 "issue_age_max", "sum_insured_range", "benefits", "limits", "exclusions"],
}

_PROMPT = """你是保險條款資料擷取程式。只根據下面提供的文字擷取，文字沒有寫的欄位一律填 null 或空陣列，禁止推測或用一般常識補。

商品：{name}（{company}）

欄位說明：
- coverage_types：這個商品提供哪些保障，只能從這些代碼選：life=身故/壽險、cancer=癌症、critical=重大疾病或重大傷病/特定傷病、accident=意外傷害（身故失能或意外醫療）、daily=住院日額、medical=實支實付或醫療費用補償/手術、ltc=長期照顧/失能扶助。產險商品（火災、車險、責任險等）不屬於這些就給空陣列。
- currency：保險金額的幣別代碼（TWD、USD、AUD、CNY 之一）。
- coverage_period：保險期間，照抄文字中描述保險期間的原文；文字只說「以保險單所載為準」就填 null。
- payment_terms：文字中明確列出的繳費年期，逐項照抄原文；沒有列出就給空陣列。
- issue_age_min / issue_age_max：文字中明確寫出「投保年齡」的下限與上限（歲）。其他年齡（例如給付生效年齡、續保年齡）不算。
- sum_insured_range：文字中明確寫出的「投保金額／保險金額範圍」原文；沒有就填 null。某項給付的上限不算，放到 limits。
- benefits：文字中出現的每一項「○○保險金」都要各列一項，name 用原文的保險金名稱，description 用一句話寫出給付條件與金額計算方式。
- limits：給付上限、次數或天數限制、自負額，各寫一句。
- exclusions：除外責任（不保事項）逐項列出，每項一句話。

再次提醒：每個值都必須能在下面的文字中找到依據。找不到就填 null 或空陣列，不要填看起來合理的值。

條款與說明文字：
{text}
"""


def call_ollama(model: str, prompt: str, timeout: int = 600) -> dict:
    body = json.dumps({
        "model": model, "prompt": prompt, "stream": False, "format": _SCHEMA,
        "options": {"num_ctx": NUM_CTX, "num_predict": NUM_PREDICT, "temperature": 0},
    }).encode("utf-8")
    req = urllib.request.Request(OLLAMA_URL, body, {"Content-Type": "application/json"})
    with urllib.request.urlopen(req, timeout=timeout) as resp:
        return json.loads(json.load(resp)["response"])


def _parse_json_reply(text: str) -> dict:
    """Model replies may carry a <think>…</think> block (Qwen3) or a ```json
    fence around the object -- keep only the outermost {...}."""
    text = re.sub(r"<think>.*?</think>", "", text or "", flags=re.S)
    start, end = text.find("{"), text.rfind("}")
    if start < 0 or end <= start:
        raise ValueError(f"no JSON object in model reply: {text[:200]!r}")
    return json.loads(text[start: end + 1])


def call_qwen_gateway(base_url: str, api_key: str, model: str, prompt: str, timeout: int = 900) -> dict:
    """The operator's own Qwen gateway (QWEN_BASE_URL / QWEN_API_KEY in
    backend/.env). Verified via its /help: Ollama-native POST /api/chat with
    `Authorization: Bearer <key>`. Sends the JSON schema as Ollama `format`
    and turns Qwen3 thinking off; if the gateway rejects those extra fields,
    retries with a plain request and relies on the prompt for JSON."""
    url = base_url.rstrip("/") + "/api/chat"
    headers = {"Content-Type": "application/json", "ngrok-skip-browser-warning": "1"}
    if api_key:
        headers["Authorization"] = f"Bearer {api_key}"
    plain = {
        "model": model,
        "messages": [{"role": "user", "content": prompt}],
        "stream": False,
    }
    structured = {**plain, "format": _SCHEMA, "think": False,
                  "options": {"num_ctx": NUM_CTX, "num_predict": NUM_PREDICT, "temperature": 0}}
    last_error: Exception | None = None
    for body_dict in (structured, plain):
        req = urllib.request.Request(url, json.dumps(body_dict).encode("utf-8"), headers)
        try:
            with urllib.request.urlopen(req, timeout=timeout) as resp:
                reply = json.load(resp)
            content = (reply.get("message") or {}).get("content") or reply.get("response") or ""
            return _parse_json_reply(content)
        except urllib.error.HTTPError as exc:
            if exc.code not in (400, 422):
                raise
            last_error = exc  # gateway didn't accept format/think/options -> plain request
    raise RuntimeError(f"Qwen gateway rejected the request: {last_error}")


def call_llm(model: str, prompt: str) -> dict:
    base_url = os.environ.get("QWEN_BASE_URL", "").strip()
    if base_url:
        return call_qwen_gateway(base_url, os.environ.get("QWEN_API_KEY", "").strip(), model, prompt)
    return call_ollama(model, prompt)


# ----------------------------------------------------------- validation

def _dedupe(items: list) -> list:
    """Drop repeated list entries (a looping model repeats one sentence)."""
    seen, out = set(), []
    for item in items:
        key = json.dumps(item, ensure_ascii=False, sort_keys=True)
        if key not in seen:
            seen.add(key)
            out.append(item)
    return out

_VALID_CURRENCIES = {"TWD", "USD", "AUD", "CNY", "EUR", "JPY", "GBP", "HKD", "NZD", "CAD", "SGD", "ZAR"}


_PAYMENT_TERM_RE = re.compile(
    r"躉繳|一次繳|[0-9一二三四五六七八九十百]+\s*年期|[0-9一二三四五六七八九十百]+\s*年繳|年繳|半年繳|季繳|月繳|"
    r"繳費至|繳至\s*[0-9一二三四五六七八九十百]+\s*歲|繳費期間"
)
_NON_PERIOD_RE = re.compile(r"保險?單(?:上|面頁)?所(?:載|記載)|以本契約.*所載")


def normalize_fields(attrs: dict) -> list[str]:
    """Shape checks for fields the grounding check can't judge: a value can
    be present in the text yet sit in the wrong field (a 7B model filed
    "第一保單年度" under payment_terms, and "以保險單所載為準" -- which states
    nothing -- as the coverage period). Returns what was removed."""
    removed = []
    kept = []
    for term in attrs.get("payment_terms") or []:
        if _PAYMENT_TERM_RE.search(str(term)):
            kept.append(term)
        else:
            removed.append(f"payment_terms: {term}")
    attrs["payment_terms"] = kept
    period = attrs.get("coverage_period")
    if period and _NON_PERIOD_RE.search(str(period)):
        removed.append(f"coverage_period: {period}")
        attrs["coverage_period"] = None
    return removed


def drop_ungrounded(attrs: dict, source: str) -> list[str]:
    """Remove model values that can't be found in the product's own text
    (scripts/audit_product_attributes.py's rules): a free 7B model will
    sometimes copy an example or read an age out of a surrender-value table.
    Returns "field: value" strings for what was dropped (kept in
    field_methods for review). Rule-derived fields are not touched."""
    from audit_product_attributes import audit_row  # same checks the audit script reports

    missing = {(field, value) for field, value, verdict in audit_row(attrs, source) if verdict == "MISSING"}
    dropped = []
    for field in ("coverage_period", "sum_insured_range"):
        if (field, str(attrs.get(field))) in missing:
            dropped.append(f"{field}: {attrs[field]}")
            attrs[field] = None
    for field, key in (("payment_terms", None), ("limits", None), ("exclusions", None), ("benefits", "name")):
        kept = []
        for item in attrs.get(field) or []:
            value = item.get(key) if key else item
            if ((f"{field}.{key}" if key else field), str(value)) in missing:
                dropped.append(f"{field}: {value}")
            else:
                kept.append(item)
        attrs[field] = kept
    age = attrs.get("issue_age")
    if age:
        for bound in ("min", "max"):
            if (f"issue_age.{bound}", str(age.get(bound))) in missing:
                dropped.append(f"issue_age.{bound}: {age[bound]}")
                age[bound] = None
        if age.get("min") is None and age.get("max") is None:
            attrs["issue_age"] = None
    return dropped


# ------------------------------------------------------------- pipeline

def _doc_text(conn, document_id: int) -> str:
    rows = conn.execute(
        "SELECT text FROM policy_document_chunks WHERE document_id = ? ORDER BY chunk_index", (document_id,)
    ).fetchall()
    if rows:
        return "\n".join(r[0] for r in rows)
    row = conn.execute("SELECT parsed_text FROM policy_documents WHERE id = ?", (document_id,)).fetchone()
    return (row[0] or "") if row else ""


def _candidates(conn, product_db_id: int | None, limit: int) -> list[tuple]:
    placeholders = ", ".join("?" for _ in TERMS_TYPES)
    sql = f"""
        SELECT p.id, p.product_name, p.company_name, p.currency
        FROM insurance_products p
        WHERE EXISTS (
            SELECT 1 FROM policy_documents d
            WHERE d.product_db_id = p.id AND d.text_status = 'parsed' AND d.document_type IN ({placeholders})
        )
    """
    params: list = list(TERMS_TYPES)
    if product_db_id:
        sql += " AND p.id = ?"
        params.append(product_db_id)
    sql += " ORDER BY p.id"
    if limit:
        sql += " LIMIT ?"
        params.append(limit)
    return conn.execute(sql, params).fetchall()


def _pick_docs(conn, product_db_id: int, types: tuple) -> list[int]:
    placeholders = ", ".join("?" for _ in types)
    rows = conn.execute(
        f"""
        SELECT d.id, (SELECT COUNT(*) FROM policy_document_chunks c WHERE c.document_id = d.id) AS n,
               LENGTH(COALESCE(d.parsed_text, '')) AS l
        FROM policy_documents d
        WHERE d.product_db_id = ? AND d.text_status = 'parsed' AND d.document_type IN ({placeholders})
        ORDER BY n DESC, l DESC
        """,
        (product_db_id, *types),
    ).fetchall()
    return [r[0] for r in rows]


def extract_one(conn, product: tuple, model: str, force: bool) -> str:
    pid, name, company, known_currency = product
    terms_ids = _pick_docs(conn, pid, TERMS_TYPES)[:1]
    dm_ids = _pick_docs(conn, pid, DM_TYPES)[:1]
    terms_text = _doc_text(conn, terms_ids[0]) if terms_ids else ""
    dm_text = _doc_text(conn, dm_ids[0])[: min(2500, MAX_PROMPT_CHARS // 3)] if dm_ids else ""
    if len(terms_text.strip()) < 200:
        return "skipped_short_text"

    source_hash = hashlib.sha1((terms_text + dm_text).encode("utf-8")).hexdigest()[:16]
    existing = conn.execute(
        "SELECT source_text_hash, extractor_version FROM product_attributes WHERE product_db_id = ?", (pid,)
    ).fetchone()
    if existing and not force and existing[0] == source_hash and existing[1] == EXTRACTOR_VERSION:
        return "unchanged"

    methods: dict[str, str] = {}
    attrs: dict = {"is_rider": rule_is_rider(name)}
    methods["is_rider"] = "name"

    waiting = rule_waiting_periods(terms_text)
    known = (known_currency or "").strip().upper()
    # insurance_products.currency from company crawls may hold non-codes
    # (e.g. "FOREIGN" for 外幣) -- only trust a real currency code.
    currency = (known if known in _VALID_CURRENCIES else "") or rule_currency(name, terms_text + dm_text)

    selected = select_sections(terms_text)
    if dm_text:
        selected = "【商品說明／DM 摘錄】\n" + dm_text + "\n\n【條款摘錄】\n" + selected
    llm = call_llm(model, _PROMPT.format(name=name, company=company, text=selected))

    attrs["coverage_types"] = [t for t in llm.get("coverage_types") or [] if t in COVERAGE_TYPES]
    llm_currency = (llm.get("currency") or "").strip().upper()
    attrs["currency"] = currency or (llm_currency if llm_currency in _VALID_CURRENCIES else None)
    methods["currency"] = "rule" if currency else "llm"
    for key in ("coverage_period", "sum_insured_range"):
        attrs[key] = llm.get(key) or None
    attrs["payment_terms"] = llm.get("payment_terms") or []
    lo, hi = llm.get("issue_age_min"), llm.get("issue_age_max")
    attrs["issue_age"] = {"min": lo, "max": hi} if (lo is not None or hi is not None) else None
    attrs["waiting_periods"] = waiting
    methods["waiting_periods"] = "rule"
    for key in ("benefits", "limits", "exclusions"):
        attrs[key] = _dedupe(llm.get(key) or [])
    attrs["payment_terms"] = _dedupe(attrs["payment_terms"])
    for key in ("coverage_types", "coverage_period", "payment_terms", "issue_age", "sum_insured_range",
                "benefits", "limits", "exclusions"):
        methods[key] = "llm"
    dropped = drop_ungrounded(attrs, terms_text + "\n" + dm_text)
    dropped += normalize_fields(attrs)
    # Applied after the grounding check: the rule's own regex is the evidence.
    rule_age = rule_issue_age(dm_text + "\n" + terms_text)
    if rule_age:  # an explicit "投保年齡 X~Y歲" beats the model's reading
        attrs["issue_age"] = rule_age
        methods["issue_age"] = "rule"
        dropped = [d for d in dropped if not d.startswith("issue_age")]
    if dropped:
        methods["_dropped_ungrounded"] = dropped

    values = (
        json.dumps(attrs, ensure_ascii=False), json.dumps(methods), json.dumps(terms_ids + dm_ids),
        source_hash, EXTRACTOR_VERSION, model,
    )
    if existing:
        conn.execute(
            """
            UPDATE product_attributes SET attributes = ?, field_methods = ?, source_document_ids = ?,
                source_text_hash = ?, extractor_version = ?, model = ?, extracted_at = datetime('now')
            WHERE product_db_id = ?
            """,
            (*values, pid),
        )
    else:
        conn.execute(
            """
            INSERT INTO product_attributes (attributes, field_methods, source_document_ids, source_text_hash,
                extractor_version, model, product_db_id)
            VALUES (?, ?, ?, ?, ?, ?, ?)
            """,
            (*values, pid),
        )
    return "extracted"


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument(
        "--model",
        default=None,
        help="Model name. Default: QWEN_MODEL from backend/.env, else qwen2.5:7b (local Ollama).",
    )
    parser.add_argument("--limit", type=int, default=0)
    parser.add_argument("--product-db-id", type=int)
    parser.add_argument("--force", action="store_true", help="Re-extract even if the source text is unchanged.")
    parser.add_argument("--sample", type=int, default=0, help="Random sample of N candidates (pilot / spot checks).")
    parser.add_argument("--max-chars", type=int, default=MAX_PROMPT_CHARS, help="Clause text sent per product.")
    parser.add_argument("--num-ctx", type=int, default=NUM_CTX, help="Model context window (tokens).")
    parser.add_argument("--num-predict", type=int, default=NUM_PREDICT,
                        help="Max generated tokens; raise it to retry products whose JSON came back truncated.")
    args = parser.parse_args()
    args.model = args.model or os.environ.get("QWEN_MODEL", "").strip() or "qwen2.5:7b"
    globals().update(MAX_PROMPT_CHARS=args.max_chars, NUM_CTX=args.num_ctx, NUM_PREDICT=args.num_predict)
    backend = os.environ.get("QWEN_BASE_URL", "").strip() or "local Ollama"

    with get_inventory_connection() as conn:
        products = _candidates(conn, args.product_db_id, args.limit)
    if args.sample:
        import random

        products = random.Random(7).sample(products, min(args.sample, len(products)))
    print(f"candidates={len(products)} model={args.model} via {backend}", flush=True)

    counts: dict[str, int] = {}
    started = time.time()
    for i, product in enumerate(products, 1):
        # One short transaction per product, so a crash or Ctrl-C keeps
        # everything extracted so far and a re-run resumes where it stopped.
        try:
            with get_inventory_connection() as conn:
                outcome = extract_one(conn, product, args.model, args.force)
        except Exception as exc:  # noqa: BLE001 -- one bad product shouldn't stop the batch
            outcome = "error"
            print(f"  error product_db_id={product[0]}: {type(exc).__name__}: {exc}", flush=True)
        counts[outcome] = counts.get(outcome, 0) + 1
        if i % 10 == 0 or i == len(products):
            rate = i / (time.time() - started)
            print(f"{i}/{len(products)} {counts} {rate:.2f}/s eta {(len(products) - i) / rate / 60:.1f} min", flush=True)
    print(json.dumps(counts))


if __name__ == "__main__":
    main()
