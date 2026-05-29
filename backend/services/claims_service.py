import json
import os
import re
from anthropic import AsyncAnthropic

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


_FALLBACK = {
    "applicable_coverages": [],
    "exclusions_to_check": ["無法解析情境，請重新描述"],
    "required_documents": [],
    "claim_steps": [],
    "important_notes": "請重新描述事故或疾病情境後再試一次。",
}


async def analyze_claim(
    scenario: str,
    holdings: list[dict],
    policy_texts: dict[str, str] | None = None,
) -> dict:
    policy_texts = policy_texts or {}

    # Build holdings section with actual policy text when available
    if holdings:
        holding_lines = []
        policy_sections = []

        for h in holdings:
            name = h.get("product_name", "")
            company = h.get("company", "")
            cat = h.get("category", "")
            amount = h.get("amount", "")
            pid = h.get("product_id", "")

            label = f"{company} {name}".strip() if company else name
            suffix = f"（{cat}）" if cat else ""
            amount_part = f"，保障金額 {amount}" if amount else ""
            holding_lines.append(f"- {label}{suffix}{amount_part}")

            # Attach real policy text if available
            if pid and pid in policy_texts:
                text = policy_texts[pid]
                policy_sections.append(
                    f"\n【{label} — 條款節錄（{len(text)} 字）】\n{text}\n"
                )

        coverage_text = "用戶持有的保險：\n" + "\n".join(holding_lines)
        if policy_sections:
            coverage_text += (
                "\n\n以下為對應保單的實際條款節錄，請根據條款內容進行分析：\n"
                + "\n".join(policy_sections)
            )
    else:
        coverage_text = "用戶未指定持有的保險（請就常見保障類型全面分析）"

    has_real_terms = bool(policy_texts)
    # Count how many holdings have real terms vs. name-only
    holdings_with_terms = [h for h in holdings if h.get("product_id") in policy_texts] if policy_texts else []
    holdings_without_terms = [h for h in holdings if h.get("product_id") not in (policy_texts or {})]

    if has_real_terms:
        terms_instruction = (
            "根據上方條款節錄進行分析，如條款中有明確文字請直接引用，若涉及不確定的解釋請用「需確認」。"
            f"注意：本次已取得 {len(holdings_with_terms)} 份條款節錄；"
            + (f"另有 {len(holdings_without_terms)} 份保單無法取得條款，請用商品慣例補充分析。" if holdings_without_terms else "")
        )
    else:
        terms_instruction = "用戶未提供實際條款（可能因保險公司網站限制無法下載），請以同類型保障的一般市場慣例進行分析，並在 important_notes 提醒用戶直接向保險公司確認實際條款。"

    prompt = f"""你是台灣保險理賠專家。根據用戶描述的情境，分析可能的理賠情況，以 JSON 格式回覆，不加任何其他文字。

用戶描述的情境：
{scenario}

{coverage_text}

{terms_instruction}

回傳格式（嚴格 JSON）：
{{
  "applicable_coverages": [
    {{
      "type": "保障類型名稱",
      "likely": true,
      "note": "一句話說明，如有條款根據請引用關鍵字"
    }}
  ],
  "exclusions_to_check": [
    "需要特別注意的除外條款或常見拒賠原因（一句話）"
  ],
  "required_documents": [
    "需要準備的文件名稱（一句話說明用途）"
  ],
  "claim_steps": [
    "理賠流程步驟（簡短動作描述）"
  ],
  "important_notes": "整體注意事項或補充說明（1-2句）"
}}

規則：
- applicable_coverages 只列出與情境有關的保障（likely: true = 可能理賠，false = 通常不賠或需確認）
- 如用戶已提供實際條款，以條款為準；未提供則依同類型商品慣例
- exclusions_to_check 列 2-4 條最重要的注意事項
- required_documents 列 3-6 項常見需準備的文件
- claim_steps 列 4-6 個步驟
- 全部繁體中文，口語化，避免法律術語
- 不要給確定性結論，用「通常」「可能」「建議確認」等措辭"""

    try:
        response = await client.messages.create(
            model="claude-haiku-4-5-20251001",
            max_tokens=1024,
            messages=[{"role": "user", "content": prompt}],
        )
        text = response.content[0].text.strip()
        data = _extract_json(text)
        if data:
            return data
    except Exception as e:
        print(f"[claims] error: {e}")

    return _FALLBACK
