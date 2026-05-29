# AI 保險 B2C — 開發規範

## 1. 絕對禁止

### 法律 / 合規
- 禁止 AI 直接推薦特定保單或比較哪家比較好（僅提供資訊，不給結論）
- 禁止聲稱本服務等同於合格保險業務員的建議
- 禁止未經授權下載或儲存第三方保險公司的商標、圖片等版權素材
- 禁止儲存用戶的身份證字號、保單號碼等高度敏感個資（MVP 階段）

### 資安
- 禁止將 API Key、資料庫密碼硬編碼進任何程式碼檔案
- 禁止將 `.env` commit 進 git（只 commit `.env.example`）
- 禁止前端直接呼叫 LLM API（Key 會暴露給用戶端）
- 禁止將用戶輸入未經驗證直接拼接進 prompt（防止 prompt injection）

### 開發流程
- 禁止直接 push 到 `main` branch（用 feature branch + PR）
- 禁止同時開始兩個功能（完成一個才開始下一個）
- 禁止在沒有 `.env.example` 的情況下新增環境變數

---

## 2. 必須遵守

### AI 回應
- 每一個 AI 回應結尾必須附帶免責聲明：「本服務提供資訊參考，非正式保險建議，請諮詢合格業務員。」
- AI 不能給出確定性結論（「你應該買 X」），只能說「根據你的情況，X 可能值得了解」
- **所有新功能的 AI 回覆必須沿用 `claude_service.py` 的 `SYSTEM_PROMPT` 格式規定**（透過 `get_advisory_response` 函數呼叫即可自動套用）
  - 禁止使用 `#` 標題符號
  - 禁止使用 `---` 水平分隔線
  - 禁止粗體文字單獨一行當標題（`**標題**` 獨立成行是禁止的）
  - 關鍵字可在句子中用 `**粗體**`，輕度強調用 `*斜體*`
  - 條列用 `- `，多項比較用 Markdown 表格
  - 保持對話語氣，不要寫成教材或文件格式
- 傳給 AI 的 prompt context 措辭應為「背景資訊供顧問參考」，避免用「請介紹/整理/說明」等指令，否則 AI 會產生文件式回覆

### 程式碼
- 所有密鑰與設定值使用環境變數（`os.getenv` / `process.env`）
- 新增 API endpoint 前先定義好 request/response schema（Pydantic model）
- 每個函數保持單一職責，不超過 50 行

### 流程
- 有破壞性改動（刪資料、改 schema、換 API）前必須先和 Claude 確認
- 功能完成後寫一個簡單的手動測試記錄再繼續下一個

---

## 3. 命名規範

| 位置 | 風格 | 範例 |
|------|------|------|
| Python 變數/函數 | snake_case | `get_product_list` |
| Python 類別 | PascalCase | `ProductService` |
| JS/TS 變數/函數 | camelCase | `fetchProductList` |
| React 元件 | PascalCase | `ProductCard` |
| 檔案名稱 | kebab-case | `product-card.tsx` |
| 常數 | UPPER_SNAKE_CASE | `MAX_PDF_SIZE` |
| 環境變數 | UPPER_SNAKE_CASE | `CLAUDE_API_KEY` |

---

## 4. 備註風格

- **只在 WHY 非顯而易見時才寫備註**（隱藏限制、特殊邏輯、繞過某個 bug）
- 不寫解釋 WHAT 的備註（好的命名本身就是文件）
- 不寫多行備註區塊，最多一行

```python
# 保險局規定：AI 不得直接推薦，只能描述商品特性
response = build_advisory_response(product, user_context)
```

---

## 5. 程式碼風格

- **Python**：用 `black` 自動格式化（`black .`）
- **JavaScript/TypeScript**：用 `prettier`（`npx prettier --write .`）
- 不做過度抽象：三個地方相似才考慮抽成共用函數
- 不加「以後可能用到」的功能，只實作現在需要的

---

## 6. Git 規範

- Branch 命名：`feat/chat-advisor`、`feat/pdf-translate`、`fix/xxx`
- Commit 訊息格式：`feat: 新增 AI 聊天顧問基本回覆流程`（不接受 `update`、`fix bug` 這類模糊訊息）
- `.gitignore` 必須包含：`.env`、`__pycache__/`、`.next/`、`node_modules/`
