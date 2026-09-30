"""Infer a product category from its name, for records whose source gives
no category (TII full index, IB disclosure).

Life-side categories reuse the vocabulary the frontend and
backend/services/rag_service.py already use (壽險保障 / 健康醫療 / 意外傷害 /
年金保險 / 投資型保險 / 還本養老 / 其他); property-side products get a small
set of 產險 categories. Keyword rules only, first hit wins -- a name with no
recognizable line falls into 其他 / 產險其他 rather than being guessed.
"""

from __future__ import annotations

import unicodedata

# (category, keywords) -- checked in order, case-insensitive for English.
_LIFE_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("投資型保險", ("變額", "投資型", "萬能", "投資連結", "投資標的", "基金", "variable", "unit-linked")),
    ("年金保險", ("年金", "annuity")),
    ("還本養老", ("還本", "養老", "生死合險", "儲蓄", "endowment")),
    ("健康醫療", ("醫療", "健康", "住院", "手術", "癌", "重大疾病", "重大傷病", "特定傷病", "失能", "殘廢", "殘扶",
               "長期照顧", "長照", "疾病", "照護", "看護", "medical", "health", "cancer")),
    ("意外傷害", ("傷害", "意外", "旅行平安", "旅平", "職業災害", "accident")),
    ("壽險保障", ("壽險", "終身保險", "定期保險", "人壽保險", "定期壽", "life insurance", "term life")),
]

# Health/accident come before the marine/engineering lines so a group
# accident rider mentioning "運輸工具" isn't filed as cargo; bare "意外" is
# deliberately NOT an accident keyword here ("電梯意外責任保險" is liability).
_PROPERTY_RULES: list[tuple[str, tuple[str, ...]]] = [
    ("車險", ("汽車", "機車", "車體", "車輛", "motor", "automobile", "vehicle")),
    ("健康醫療", ("醫療", "健康", "住院", "手術", "癌", "疾病", "失能", "看護", "medical", "health")),
    ("意外傷害", ("傷害", "旅行平安", "旅平", "personal accident")),
    ("海上及貨物", ("海上", "貨物", "船體", "船舶", "漁船", "遊艇", "運輸", "貨櫃", "運送", "航空", "飛機",
                "cargo", "hull", "marine", "transit", "aviation", "institute")),
    ("工程保險", ("工程", "營造", "安裝", "機械", "鍋爐", "電子設備", "營建機具", "erection", "contractor",
              "construction", "machinery", "boiler", "engineering")),
    ("責任保險", ("責任", "董監", "專業", "賠償", "liability", "indemnity", "d&o", "directors", "officers")),
    ("火災及住宅", ("火災", "住宅", "地震", "颱風", "洪水", "消防", "fire", "earthquake", "property damage")),
    ("信用保證", ("保證", "信用", "誠實", "竊盜", "現金", "fidelity", "credit", "bond", "surety", "money", "theft")),
]

LIFE_DEFAULT = "其他"
PROPERTY_DEFAULT = "產險其他"


def infer_category(product_name: str, company_type: str) -> str:
    """`company_type` is "life" | "property" | "" (unknown company -- then
    the property rules are tried only if no life rule matches, since most
    unknown-company records are English marine/property clauses)."""
    text = unicodedata.normalize("NFKC", product_name or "").lower()

    def first_hit(rules):
        for category, keywords in rules:
            if any(k.lower() in text for k in keywords):
                return category
        return None

    if company_type == "life":
        return first_hit(_LIFE_RULES) or LIFE_DEFAULT
    if company_type == "property":
        return first_hit(_PROPERTY_RULES) or PROPERTY_DEFAULT
    return first_hit(_PROPERTY_RULES) or first_hit(_LIFE_RULES) or LIFE_DEFAULT
