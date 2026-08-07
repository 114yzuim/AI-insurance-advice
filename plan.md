# 待辦計畫

## RAG 評估指標（論文用）

**為什麼要做：** 論文需要數字證明 hybrid search 比 naive search 好。沒有評估指標就只是「有做這個功能」，無法說服審稿人。

### 步驟

1. **建測試集**（30-50 筆）
   - 每筆：查詢字串 + 預期正確商品 ID 列表
   - 方式：手動建 or 用 LLM 生成 synthetic queries
   - 存成 `scripts/eval_dataset.json`

2. **對三個版本跑評估**
   - Naive Vector Search（原始 MiniLM，單純 cosine）
   - Hybrid Search（BGE-M3 + BM25 + RRF，目前版本）
   - Profile-Augmented Hybrid（加上 profile 的版本）

3. **計算指標**
   - **Hit@5**：正確商品有沒有出現在 top-5
   - **MRR**（Mean Reciprocal Rank）：正確商品排在第幾

4. **輸出論文用表格**

| 方法 | Hit@5 | MRR |
|------|-------|-----|
| Naive Vector Search | ? | ? |
| + BM25 Hybrid | ? | ? |
| + Profile Augmented | ? | ? |

---

## Re-ranking（評估完之後再決定）

用 cross-encoder 對 top-20 重新打分取 top-5。
只有在評估指標顯示有改善才值得加進論文。

- 模型：`cross-encoder/mmarco-mMiniLMv2-L12-H384-v1`（支援中文）
- 架構：Retrieve top-20 → Re-rank → Return top-5
