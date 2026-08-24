import json
import os
import re
from anthropic import AsyncAnthropic
from services.rag_service import recommend_products_for_assessment

client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))


def _extract_json(text: str) -> dict | None:
    try:
        return json.loads(text)
    except Exception:
        pass
    block = re.search(r"```(?:json)?\s*(\{.*?\})\s*```", text, re.DOTALL)
    if block:
        try:
            return json.loads(block.group(1))
        except Exception:
            pass
    brace = re.search(r"\{.*\}", text, re.DOTALL)
    if brace:
        try:
            return json.loads(brace.group())
        except Exception:
            pass
    return None


QUESTION_LABELS = {
    "age": "精確年齡",
    "relation": "家庭角色",
    "monthly_income": "每月收入",
    "monthly_expense": "家庭每月必要支出",
    "dependents_count": "扶養人數",
    "mortgage_balance": "房貸或主要負債餘額",
    "current_policy_status": "既有保單資料狀態",
    "current_policy_types": "已知保單類型",
    "health_status": "健康狀況",
    "family_medical_history": "家族重大疾病史",
    "monthly_insurance_budget": "每月可接受保費預算",
    "report_focus": "保單健診重點",
    "claim_service_need": "理賠服務需求",
    "notes": "補充說明",
    "marital": "婚姻狀況",
    "children": "扶養小孩",
    "income": "每月收入",
    "job": "工作性質",
    "debt": "房貸/重大債務",
    "health": "健康狀況",
    "budget": "每月保險預算",
}

_FALLBACK_ITEMS = [
    {"key": "accident_coverage",  "priority": 1, "amount": 200,   "unit": "萬元",  "premium_range": "約 100–200 元/月",   "monthly_premium_mid": 150,  "within_budget": True,  "reason": "CP 值最高的基本保障，建議優先投保"},
    {"key": "medical_daily",      "priority": 2, "amount": 1500,  "unit": "元/日", "premium_range": "約 500–900 元/月",   "monthly_premium_mid": 700,  "within_budget": True,  "reason": "住院頻率高，可有效減輕醫療費用負擔"},
    {"key": "disability_monthly", "priority": 3, "amount": 20000, "unit": "元/月", "premium_range": "約 800–1,500 元/月", "monthly_premium_mid": 1150, "within_budget": False, "reason": "保護收入來源，預算充裕後優先補足"},
    {"key": "cancer_coverage",    "priority": 4, "amount": 50,    "unit": "萬元",  "premium_range": "約 500–1,000 元/月", "monthly_premium_mid": 750,  "within_budget": False, "reason": "癌症發生率高，建議逐步納入規劃"},
    {"key": "life_coverage",      "priority": 5, "amount": 200,   "unit": "萬元",  "premium_range": "約 150–300 元/月",   "monthly_premium_mid": 225,  "within_budget": False, "reason": "視家庭責任調整，單身需求較低"},
]


def _make_fallback_member(name: str) -> dict:
    keys = [item["key"] for item in _FALLBACK_ITEMS]
    return {
        "name": name,
        "items": _FALLBACK_ITEMS,
        "budget_note": "無法解析，以下為通用建議。",
        "summary": "建議優先投保意外險與醫療保障，再視預算逐步補足失能與癌症保障。",
        "recommended_products": recommend_products_for_assessment(keys),
    }


async def get_family_assessment(members: list[dict]) -> dict:
    """Assess all family members in one prompt, with shared family context."""

    members_text = ""
    for i, m in enumerate(members, 1):
        answers_text = "\n".join(
            f"  - {QUESTION_LABELS.get(k, k)}：{v}" for k, v in m["answers"].items()
        )
        members_text += f"\n成員 {i}（{m['name']}）：\n{answers_text}\n"

    n = len(members)
    member_example = json.dumps(
        {
            "name": "本人",
            "items": [
                {
                    "key": "accident_coverage",
                    "priority": 1,
                    "amount": 200,
                    "unit": "萬元",
                    "premium_range": "約 100–200 元/月",
                    "monthly_premium_mid": 150,
                    "within_budget": True,
                    "reason": "一句話",
                }
            ],
            "budget_note": "...",
            "summary": "1-2 句摘要",
        },
        ensure_ascii=False,
        indent=2,
    )

    prompt = f"""你是台灣保險規劃顧問。根據以下 {n} 位家庭成員資料，給出每人的保障建議，並提供家庭整體摘要。以 JSON 格式回覆，不加任何其他文字。

家庭成員資料：
{members_text}
回傳格式（嚴格 JSON）：
{{
  "family_summary": "2-3 句整體家庭保障規劃摘要，說明家庭角色分工與預算分配重點",
  "members": [
    {member_example}
  ]
}}

members 陣列必須包含且只包含輸入的 {n} 位成員，順序相同。
每位成員的 items 必須包含且只包含這 5 個 key（按優先順序排列）：
- accident_coverage（意外保額，萬元）
- medical_daily（住院醫療日額，元/日）
- disability_monthly（失能月給付，元/月）
- cancer_coverage（癌症一次給付，萬元）
- life_coverage（壽險保額，萬元）

規則：
- 考慮家庭脈絡：主要薪資來源的壽險金額應能支撐整個家庭開銷
- amount 整數，符合各成員收入與預算的現實承擔能力
- premium_range 格式「約 X–Y 元/月」，monthly_premium_mid 為區間中間值整數
- within_budget 根據該成員自己填寫的預算判斷
- reason 繁體中文，口語化，一句話
- 台灣保費行情（30 歲參考）：意外險 200 萬約 100–200/月；醫療日額 1000 元約 400–700/月；癌症 100 萬約 600–1200/月；失能月給 2 萬約 1000–1800/月；定期壽險 500 萬約 200–500/月"""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=4096,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        data = _extract_json(text)
        if data and "members" in data:
            for member in data["members"]:
                member["items"] = sorted(
                    member.get("items", []), key=lambda x: x.get("priority", 9)
                )
                priority_keys = [item["key"] for item in member["items"]]
                member["recommended_products"] = recommend_products_for_assessment(priority_keys)
            return data
    except Exception as e:
        print(f"[needs_assessment] error: {e}")

    return {
        "family_summary": "無法完成評估，以下為各成員通用建議，請重新嘗試。",
        "members": [_make_fallback_member(m["name"]) for m in members],
    }
