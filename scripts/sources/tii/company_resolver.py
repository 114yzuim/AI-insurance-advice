"""Infer the insurance company for a TII index record from its product name.

TII's public full index (`ResultQueryAll.aspx`, see
scripts/ingest_tii_result_pages.py) has no company column at all, and the
per-product DetailList.aspx page that does is CAPTCHA-gated (see
scripts/resolve_tii_details.py) -- so the product name is the only signal we
have. In practice nearly every name starts with the company that filed it
("富邦產物…", "國泰人壽…", "HOTAI MARINE CARGO …").

Rules, tried in order (first hit wins):
  1. cjk_prefix     -- a known Chinese company name/alias at the start of the
                       name, after an optional short ASCII product code
                       ("SB002富邦產物…").
  2. english_prefix -- a known English company name at the start.
  3. cjk_contains   -- a known Chinese company name anywhere in the name
                       (e.g. an English clause title with "(和泰產物…)").
  4. brand_prefix   -- a bare brand with no 人壽/產物 suffix, only for brands
                       that exist as exactly one company ("兆豐網路損失…").
  5. brand_line     -- a bare brand that has BOTH a life and a property
                       company (富邦/國泰/...), disambiguated by a product line
                       only one side may legally sell: 海上/貨物/火災/... are
                       property-only, 壽險/年金/利率變動/... are life-only.
                       Health/accident lines (both may sell) stay unknown.
  6. unknown        -- nothing matched; company_name stays "" and the record
                       is still imported (never dropped).

Company names are returned as printed-era canonical short names (e.g.
中國人壽, 國華人壽 stay as they are even though those companies were later
merged into others) -- mapping a historical filer to its successor is a
business decision, not something to guess at here. The only merges done are
spelling variants / typos / renames of the *same* legal entity, listed
explicitly below. Extend these tables from evidence, never by guess.

Pure functions, no I/O -- see scripts/resolve_tii_companies.py for the
batch runner and report.
"""

from __future__ import annotations

import re
import unicodedata
from dataclasses import dataclass

# canonical short name -> company type
CANONICAL_COMPANIES: dict[str, str] = {
    # life
    "台灣人壽": "life", "國泰人壽": "life", "富邦人壽": "life", "南山人壽": "life",
    "凱基人壽": "life", "新光人壽": "life", "全球人壽": "life", "三商美邦人壽": "life",
    "遠雄人壽": "life", "元大人壽": "life", "保誠人壽": "life", "安達人壽": "life",
    "安聯人壽": "life", "友邦人壽": "life", "宏泰人壽": "life", "臺銀人壽": "life",
    "第一金人壽": "life", "法國巴黎人壽": "life", "合作金庫人壽": "life", "華南永昌人壽": "life",
    "中華郵政": "life", "中國人壽": "life", "中泰人壽": "life", "康健人壽": "life",
    "國華人壽": "life", "中國信託人壽": "life", "保德信國際人壽": "life", "台新人壽": "life",
    "幸福人壽": "life", "國寶人壽": "life", "大都會國際人壽": "life", "興農人壽": "life",
    "紐約人壽": "life", "宏利人壽": "life", "安泰人壽": "life", "朝陽人壽": "life",
    "美國人壽": "life", "統一安聯人壽": "life", "環球瑞泰人壽": "life", "中央人壽": "life",
    "匯豐人壽": "life", "第一英傑華人壽": "life", "蘇黎世國際人壽": "life",
    # property
    "富邦產物": "property", "兆豐產物": "property", "國泰世紀產物": "property", "臺灣產物": "property",
    "明台產物": "property", "台壽保產物": "property", "新安東京海上產物": "property", "蘇黎世產物": "property",
    "華南產物": "property", "泰安產物": "property", "和泰產物": "property", "新光產物": "property",
    "美亞產物": "property", "南山產物": "property", "中國信託產物": "property", "友邦產物": "property",
    "安達產物": "property", "第一產物": "property", "三井住友產物": "property", "美商聯邦產物": "property",
    "亞洲產物": "property", "華山產物": "property", "法國巴黎產物": "property", "龍平安產物": "property",
    "中央產物": "property", "太平產物": "property", "台灣區漁船產物": "property", "旺旺友聯產物": "property",
}

# Spelling variants / legal-form prefixes / typos seen in real TII names ->
# canonical. Every canonical name is also its own alias (added below).
_CJK_ALIASES: dict[str, str] = {
    "國泰產物": "國泰世紀產物",
    "國泰產險": "國泰世紀產物",
    "法商法國巴黎人壽": "法國巴黎人壽",
    "法國法國巴黎人壽": "法國巴黎人壽",
    "法商法國巴黎產物": "法國巴黎產物",
    "郵政簡易人壽": "中華郵政",
    "有限責任台灣區漁船產物": "台灣區漁船產物",
    "富邦產險": "富邦產物",
    "和泰產險": "和泰產物",
    "華南產險": "華南產物",
    "兆豐產險": "兆豐產物",
    "新安東京海上產險": "新安東京海上產物",
    "台壽保產險": "台壽保產物",
    "保徳信國際人壽": "保德信國際人壽",
    "滙豐人壽": "匯豐人壽",
    # doubled/truncated typos in the source itself
    "兆兆豐產物": "兆豐產物",
    "富邦富邦產物": "富邦產物",
    "蘇蘇黎世產物": "蘇黎世產物",
    "黎世產物": "蘇黎世產物",
}
for _name in CANONICAL_COMPANIES:
    _CJK_ALIASES.setdefault(_name, _name)
# Longest first so "法商法國巴黎人壽" wins over any shorter overlapping alias.
_CJK_ALIAS_ORDER = sorted(_CJK_ALIASES, key=len, reverse=True)

# (regex anchored at the start of the name, canonical). Order matters: the
# LIFE-specific entries must precede the brand's general (property) entry.
# "Life Science" is a property/liability product line ("Chubb Life Science
# Liability ..."), not the life-insurance company -- hence the lookahead.
_ENGLISH_PREFIXES: list[tuple[re.Pattern, str]] = [
    (re.compile(p, re.I), c)
    for p, c in [
        (r"nan\s*shan\s+life\b(?!\s+science)", "南山人壽"),
        (r"nan\s*shan\s+general", "南山產物"),
        (r"south\s+china", "華南產物"),
        (r"(aig|chartis|aiu)\b", "美亞產物"),  # Chartis = 美亞's pre-2012 name
        (r"cathay\s+life\b(?!\s+science)", "國泰人壽"),
        (r"cathay\s+century", "國泰世紀產物"),
        (r"(tokio\s+marine|tmnewa\b|newa\b)", "新安東京海上產物"),
        (r"fubon\s+life\b(?!\s+science)", "富邦人壽"),
        (r"fubon\b", "富邦產物"),
        (r"ctbc\s+life\b(?!\s+science)", "中國信託人壽"),
        (r"ctbc\b", "中國信託產物"),
        (r"(taiwan\s+fire|tfmi\b)", "臺灣產物"),
        (r"chung\s+kuo\b", "兆豐產物"),  # 中國產物 -> merged into 兆豐產物; flagged in report
        (r"hotai\b", "和泰產物"),
        (r"zurich\b", "蘇黎世產物"),
        (r"chubb\s+life\b(?!\s+science)", "安達人壽"),
        (r"chubb\b", "安達產物"),
        (r"federal\s+insurance", "美商聯邦產物"),
        (r"tlg\b", "台壽保產物"),
        (r"(mitsui\s+sumitomo|msig\b)", "三井住友產物"),
        (r"taian\b", "泰安產物"),
        (r"shin\s*kong\s+life\b(?!\s+science)", "新光人壽"),
        (r"shin\s*kong\b", "新光產物"),
        (r"ming\s*tai\b", "明台產物"),
        (r"mega\s+insurance", "兆豐產物"),
        (r"first\s+insurance", "第一產物"),
    ]
]

# Canonical names whose English mapping merges a renamed/merged entity --
# surfaced separately in the report so a human can confirm.
HISTORICAL_ENGLISH_MAPPINGS = {"chung kuo": "兆豐產物"}

# Bare brands that correspond to exactly one company (no life/property
# ambiguity). Deliberately excludes 富邦/國泰/新光/南山/安達/中國信託/友邦
# (both a life and a property company) and generic words like 臺灣/亞洲.
_UNIQUE_BRANDS: dict[str, str] = {
    "兆豐": "兆豐產物", "明台": "明台產物", "泰安": "泰安產物", "和泰": "和泰產物",
    "華山": "華山產物", "美亞": "美亞產物", "台壽保": "台壽保產物", "三井住友": "三井住友產物",
    "新安東京海上": "新安東京海上產物", "蘇黎世產": "蘇黎世產物",
}

# Brands with both a life and a property company -> (life, property).
_DUAL_BRANDS: dict[str, tuple[str, str]] = {
    "富邦": ("富邦人壽", "富邦產物"), "國泰": ("國泰人壽", "國泰世紀產物"),
    "新光": ("新光人壽", "新光產物"), "南山": ("南山人壽", "南山產物"),
    "安達": ("安達人壽", "安達產物"), "中國信託": ("中國信託人壽", "中國信託產物"),
    "友邦": ("友邦人壽", "友邦產物"), "蘇黎世": ("蘇黎世國際人壽", "蘇黎世產物"),
    "法國巴黎": ("法國巴黎人壽", "法國巴黎產物"),
}
# Lines only one kind of insurer may sell under Taiwan's life/non-life split.
_PROPERTY_ONLY_LINES = (
    "海上", "貨物", "火災", "汽車", "機車", "工程", "營造", "責任", "運送", "船",
    "動產", "住宅", "地震", "竊盜", "保證保險", "信用保險", "航空", "颱風", "洪水",
)
# Health/accident lines may be sold by either side, and their names often
# contain a property-looking word ("航空飛行團體傷害保險", "火災意外傷害") --
# any of these makes the name ambiguous, so brand_line refuses to guess.
_EITHER_SIDE_LINES = ("傷害", "健康", "醫療", "意外", "疾病", "住院", "手術", "癌", "失能", "長期照顧", "旅行平安", "旅平")
_LIFE_ONLY_LINES = ("壽險", "終身保險", "年金", "利率變動", "還本", "投資型", "變額", "萬能", "生死合險", "養老保險")

_LEADING_CODE_RE = re.compile(r"^[A-Za-z0-9\s\-_.()（）]{0,12}?(?=[一-鿿])")


@dataclass(frozen=True)
class CompanyMatch:
    company_name: str  # canonical short name, "" if unknown
    company_type: str  # "life" | "property" | ""
    method: str  # cjk_prefix | english_prefix | cjk_contains | brand_prefix | unknown
    matched: str = ""  # the literal text that matched


def _normalize(name: str) -> str:
    return unicodedata.normalize("NFKC", name or "").strip()


def _hit(canonical: str, method: str, matched: str) -> CompanyMatch:
    return CompanyMatch(canonical, CANONICAL_COMPANIES[canonical], method, matched)


def resolve_company(product_name: str) -> CompanyMatch:
    name = _normalize(product_name)
    if not name:
        return CompanyMatch("", "", "unknown")

    # 1. Chinese alias at the start (optionally after a short product code).
    code = _LEADING_CODE_RE.match(name)
    body = name[code.end():] if code else name
    for alias in _CJK_ALIAS_ORDER:
        if body.startswith(alias):
            return _hit(_CJK_ALIASES[alias], "cjk_prefix", alias)

    # 2. English company name at the start.
    for pattern, canonical in _ENGLISH_PREFIXES:
        match = pattern.match(name)
        if match:
            return _hit(canonical, "english_prefix", match.group(0))

    # 3. Chinese alias anywhere.
    for alias in _CJK_ALIAS_ORDER:
        if len(alias) >= 4 and alias in name:
            return _hit(_CJK_ALIASES[alias], "cjk_contains", alias)

    # 4. Unambiguous bare brand at the start.
    for brand in sorted(_UNIQUE_BRANDS, key=len, reverse=True):
        if body.startswith(brand):
            return _hit(_UNIQUE_BRANDS[brand], "brand_prefix", brand)

    # 5. Dual brand, disambiguated by a one-side-only product line.
    for brand, (life, prop) in sorted(_DUAL_BRANDS.items(), key=lambda kv: len(kv[0]), reverse=True):
        if body.startswith(brand):
            if any(k in body for k in _EITHER_SIDE_LINES):
                break
            is_property = any(k in body for k in _PROPERTY_ONLY_LINES)
            is_life = any(k in body for k in _LIFE_ONLY_LINES)
            if is_property != is_life:  # exactly one side -> safe
                return _hit(prop if is_property else life, "brand_line", brand)
            break

    return CompanyMatch("", "", "unknown")
