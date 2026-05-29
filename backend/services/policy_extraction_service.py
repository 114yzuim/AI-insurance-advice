import json
import os
import re
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))

BASELINES = {
    "life_coverage": 500,       # 萬元
    "medical_daily": 3000,      # 元/日
    "accident_coverage": 200,   # 萬元
    "cancer_coverage": 100,     # 萬元
    "disability_monthly": 30000, # 元/月
}

_EMPTY = {
    "policy_name": "未知",
    "company": "未知",
    "life_coverage": 0,
    "medical_daily": 0,
    "accident_coverage": 0,
    "cancer_coverage": 0,
    "disability_monthly": 0,
    "notes": "無法解析保單內容",
}


async def extract_policy_coverage(pdf_text: str) -> dict:
    prompt = f"""請從以下保單條款文字中，萃取保障資訊，以 JSON 格式回覆，不要加任何其他文字。

保單文字：
{pdf_text[:8000]}

回傳格式（嚴格 JSON，找不到的欄位填 0 或「未知」）：
{{
  "policy_name": "保單名稱",
  "company": "保險公司名稱",
  "life_coverage": 0,
  "medical_daily": 0,
  "accident_coverage": 0,
  "cancer_coverage": 0,
  "disability_monthly": 0,
  "notes": "備註"
}}

欄位說明：
- life_coverage：壽險身故保額，單位萬元（例如 500 萬填 500）
- medical_daily：住院醫療日額，單位元/日（例如 1500 元填 1500）
- accident_coverage：意外傷害保額，單位萬元
- cancer_coverage：癌症一次給付保額，單位萬元
- disability_monthly：失能/殘廢月給付，單位元/月
- 金額若以元標示請自行換算（life/accident/cancer 要換萬元）"""

    try:
        response = await client.messages.create(
            model="claude-sonnet-4-6",
            max_tokens=512,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        match = re.search(r"\{.*\}", text, re.DOTALL)
        if match:
            return json.loads(match.group())
    except Exception:
        pass
    return _EMPTY.copy()


def build_gaps(totals: dict) -> list[str]:
    gaps = []
    labels = {
        "life_coverage": ("壽險保障", totals["life_coverage"], BASELINES["life_coverage"], "萬元"),
        "medical_daily": ("住院醫療日額", totals["medical_daily"], BASELINES["medical_daily"], "元/日"),
        "accident_coverage": ("意外保障", totals["accident_coverage"], BASELINES["accident_coverage"], "萬元"),
        "cancer_coverage": ("癌症保障", totals["cancer_coverage"], BASELINES["cancer_coverage"], "萬元"),
        "disability_monthly": ("失能保障", totals["disability_monthly"], BASELINES["disability_monthly"], "元/月"),
    }
    for key, (name, val, base, unit) in labels.items():
        if val == 0:
            gaps.append(f"**{name}**：目前無保障，建議基準為 {base:,} {unit}")
        elif val < base * 0.5:
            gaps.append(f"**{name}**：目前 {val:,} {unit}，嚴重不足（建議 {base:,} {unit}）")
        elif val < base:
            gaps.append(f"**{name}**：目前 {val:,} {unit}，略低於建議基準 {base:,} {unit}")
    return gaps
