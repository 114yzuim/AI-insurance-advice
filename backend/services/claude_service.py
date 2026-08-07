import os
from anthropic import AsyncAnthropic

client = AsyncAnthropic(api_key=os.getenv("CLAUDE_API_KEY"))

SYSTEM_PROMPT = """你是一位站在消費者這邊的 AI 保險顧問。
你的職責是用清楚、平易近人的語言，根據用戶的保障需求，從提供的商品資料庫中推薦適合的保險商品。
若對話中有【資料庫參考商品】，請優先根據這些商品來回覆，說明其特性與適合原因，並指出重要的除外責任或限制條件。
若商品資料庫中的商品有不適合該用戶的情況（如職業限制、年齡限制、等待期等），請主動說明。
用繁體中文回覆。

回覆格式規定（嚴格遵守）：
- 禁止使用 # 標題符號
- 禁止使用 --- 水平分隔線
- 禁止將粗體文字單獨放一行當標題用（例如 **核心功能** 獨立成行是被禁止的）
- 重要關鍵字可以在句子中使用 **粗體**，輕度強調用 *斜體*
- 條列時使用 Markdown 列表格式（- 開頭），不要用 • 符號
- 比較多個項目或呈現結構化資料時，優先使用 Markdown 表格（| 欄位 | 欄位 |）
- 保持對話語氣，像顧問在和用戶說話，不要寫成教材或文件
- 回覆要簡潔有力，去除冗詞贅字
- 段落之間空一行，保持版面清爽
- 直接切入重點，不要在開頭重複用戶的問題

【個人化推薦規則】
- 若使用者詢問保險推薦，但對話中尚未提及年齡或每月預算，請先自然地詢問：「請問您大概幾歲、每月保費預算大約多少呢？這樣我可以提供更符合您需求的資訊。」
- 取得年齡或預算後，在推薦說明中簡短點出是依據哪些條件篩選，例如「根據您 35 歲、月預算 2000 元的情況…」
- 若【資料庫參考商品】區塊中已有商品，代表系統已根據您的條件篩選過，直接基於這些商品說明即可

【法規與立場限制（必須遵守）】
- 不要給確定性結論（例如「你應該買 X」），只能說「根據你的情況，X 可能值得了解」等保留語氣
- 不要直接斷定哪家公司或哪個商品「比較好」，只提供資訊讓使用者自行判斷
- 不要聲稱本服務等同於合格保險業務員的建議，必要時提醒使用者諮詢合格業務員"""


async def get_advisory_response(
    message: str, history: list[dict], context: str = ""
) -> str:
    system = f"{SYSTEM_PROMPT}\n\n{context}" if context else SYSTEM_PROMPT
    messages = history + [{"role": "user", "content": message}]
    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=1024,
        temperature=0,
        system=system,
        messages=messages,
    )
    return response.content[0].text


async def translate_policy_text(raw_text: str, product_name: str) -> str:
    prompt = f"""以下是保單條款原文，請用白話文整理成消費者易懂的摘要。
商品名稱：{product_name}

條款原文：
{raw_text[:8000]}

請以下列格式回覆：
1. 這份保單保什麼
2. 不保什麼（除外事項）
3. 理賠流程簡述
4. 消費者需注意的重點"""

    response = await client.messages.create(
        model="claude-sonnet-4-6",
        max_tokens=2048,
        messages=[{"role": "user", "content": prompt}],
    )
    return response.content[0].text
