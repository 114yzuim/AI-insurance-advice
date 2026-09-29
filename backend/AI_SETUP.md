# AI provider 設定

後端使用 `services/llm_service.py` 統一呼叫 AI。商品比較、對話、條款摘要、背景資料擷取、需求分析與理賠情境分析共用設定；商品資料庫與檢索流程沿用既有實作。

1. 安裝 `requirements.txt` 的套件。
2. 複製 `.env.example` 為 `.env`，在本機填入 `OPENAI_API_KEY`。
3. 設定 `LLM_PROVIDER=openai`，重新啟動後端。

```dotenv
LLM_PROVIDER=openai
OPENAI_API_KEY=在本機填入平台建立的Key
OPENAI_MODEL=gpt-6-astra
OPENAI_FAST_MODEL=gpt-4.1-mini
OPENAI_REASONING_EFFORT=low
```

`OPENAI_MODEL` 用於主要回答、條款摘要及保單欄位擷取；`OPENAI_FAST_MODEL` 用於客戶背景擷取、需求分析與理賠情境分析。OpenAI 使用 Responses API，設定 `store=false`，保留原本繁體中文提示與 JSON 解析流程。

GPT-6 使用 `low` 推理強度，不傳入 `temperature`；輸出 token 上限包含推理 token，因此主要模型額外預留 2,048 tokens。帳號可用模型及實際費用以 OpenAI 平台為準。

`GET /` 可確認 `ai_provider`、`ai_model`、`ai_fast_model` 與 `api_key_set`，不會回傳 Key。`api_key_set` 僅表示有設定，不能證明權限或餘額可用。

如需手動切回原供應商，設定 `LLM_PROVIDER=claude` 並保留 `CLAUDE_API_KEY` 後重啟。呼叫失敗時不會自動將資料改送另一家供應商。未設定 `LLM_PROVIDER` 的既有部署仍維持 Claude。

不要將 `.env` 提交到 Git，或把 Key 放在前端 `NEXT_PUBLIC_*` 變數中。網站 API 呼叫按 OpenAI API 計費，與 ChatGPT／Codex 訂閱登入不同。

驗證方式（在 backend 目錄）：

```console
python -m unittest discover -s tests -p "test_llm_service.py" -v
```

官方文件：
- https://developers.openai.com/api/docs/quickstart
- https://developers.openai.com/api/docs/guides/latest-model
- https://learn.chatgpt.com/docs/auth
