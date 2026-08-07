# 自由配 / 設定配 — 可交付配置模組(設計 spec)

> 版本 v0.2 · 2026-06-04
> 目的:把「保經 Planning Studio」原型裡的 **自由配（Free Allocation）** 與 **設定配（Constrained Allocation）** 兩個概念,做成一個自包含、低耦合、好嵌入的模組,交給同學的系統整合。
> 原則:**先簡單、好解釋、能整合在一起**;估算與求解的細部數值後續再調。
> **v0.2 變更**:依 2026-05-01 會議記錄(邱昭彰教授)修正為**兩層模型** —— 先「個別獨立算 A/B/C」(不加總 100),再由自由配整合成「加總 100% 的配置」。詳見第 2 節。

---

## 1. 背景與目標

- 來源:`O/`(= 已刪除的 New-1 原型的 claude design 設計檔)裡的 `AllocScreen`(見 `screens-2.jsx`)。原型中兩個模式都是**寫死的展示值**,沒有真的引擎。
- 目標系統(同學):**前端 React/TSX + 後端 Python**,且**沒有現成的 ABC 配置/試算引擎** → 本模組要連邏輯一起提供。
- ABC 三桶定義:
  - **A 金融 / 投資** — ETF、債券、定存等資產累積
  - **B 保險 / 年金** — 儲蓄險、年金、投資型保單
  - **C 醫療 / 長照** — 醫療險、失能、長照給付

### 1.1 會議定調的模式關係(2026-05-01)

教授把流程定為**兩層 + 兩種輸出模式**:

| 層 / 模式 | 定義 | 加總 100? | 用途 |
|---|---|---|---|
| **個別分析(mode one)** | A、B、C **各自獨立純算**(純算 A 是多少、純算 B 是多少、純算 C 是多少) | **否** | 保經內部 sandbox;**作為自由配的「背景輸入」**,不是拿來自己做最佳化 |
| **自由配 / AI 自動(mode two)** | AI 讀個別分析結果,**整合成加總 100% 的配置**(例:A42 / B38 / C20) | **是** | 教授定調「**才是主要的**」 |
| **設定配(constrained)** | 在自由配之上,保經加條件(下限/上限/必含)再求解,一樣輸出 100% | **是** | 保經想設限時用 |

> 原話佐證:個別「純粹 A 是多少純粹 B 是多少純粹 C 是多少」(12:50);「mode one … 要當作 mode two 的背景去計算」(13:48);自由配「總個別 ABC 算完了以後 … 剛好可以湊到 100%」(11:55)。

### 範圍
- **做**:兩層資料模型、個別需求估算(Layer 1)、自由配整合(Layer 2)、設定配求解器、API 契約、React/TSX 前端、整合文件、後端測試。
- **不做(本版)**:達標/不達標的「建議增加投入金額」邏輯(列後續,見第 9 節)、流動性保留納入三桶計算、與同學系統客戶物件的實際欄位對映。

---

## 2. 資料模型(對外契約)

前端 TS 型別與後端 pydantic 模型欄位一一對齊。**核心是兩層**:`IndependentNeeds`(個別、不加總)→ `Allocation`(整合、加總 100)。

| 型別 | 欄位 | 說明 |
|---|---|---|
| `ClientInputs` | `age`, `retireAge`, `monthlyInvestable`, `dependents`, `riskTolerance(low\|mid\|high)`, `hasMedicalCoverage(bool)`, `hasLifeCoverage(bool)` | 估算所需的客戶訊號 |
| `IndependentNeeds` | `a`, `b`, `c`(number,**各自獨立、不加總 100**) | **Layer 1 / 個別分析**:純算每桶的需求強度,即教授說的「mode one 背景」 |
| `Allocation` | `a`, `b`, `c`(number,**加總 = 100**) | **Layer 2 輸出**:自由配 / 設定配的配置比例 |
| `Constraint` | `id`, `label`, `kind(floor\|cap\|must_include\|liquidity)`, `bucket(A\|B\|C\|null)`, `value(number)`, `active(bool)` | 設定配的單一條件 |
| `AllocationResult` | `allocation`, `baseline`, `needs`, `feasible(bool)`, `binding[]`, `adjustments[]`, `explanation(str)`, `error?(str)` | 求解結果,可解釋;`needs` 帶出 Layer 1 供顯示/追溯 |

---

## 3. 自由配 — 兩層估算(規則式、確定性)

### Layer 1 — 個別需求 `independent_needs(client) -> IndependentNeeds`
每桶**各自獨立**算,刻意**不**正規化(對應教授的「個別分析 / mode one」)。本版預設常數(簡單、可解釋,日後可調):

```
yearsToRetire = max(0, retireAge - age)

needA = 30 + min(yearsToRetire, 30)                              # 金融:年期越長 → 純需求越高
needB = 18 + dependents * 3 + (riskTolerance == 'low' ? 6 : 0)   # 保險:扶養 + 保守加碼
needC = 8  + max(0, age - 40) * 0.4 + (hasMedicalCoverage ? 0 : 6)  # 醫療:年齡 + 醫療缺口
```
這三個值**互相獨立、不加總 100**(它們是「純算 A / 純算 B / 純算 C」)。

### Layer 2 — 自由配整合 `free_allocate(needs) -> Allocation`
把 Layer 1 的三個獨立需求**正規化成加總 100%**:
```
total = needA + needB + needC
a, b, c = round(100 * each / total)   # 四捨五入後把餘數補到最大桶,確保剛好 100
```

**驗算(demo 客戶 林志豪:42→65 退、扶養1、有醫療、風險中)**
- Layer 1 個別需求:**needA=53 / needB=21 / needC=8.8**(各自獨立,合計 82.8,**不是** 100)
- Layer 2 自由配:正規化 → **A 64 / B 25 / C 11**(加總 100)

> 估算常數為「合理預設起點」。日後若保經提供真實個別計算邏輯/對照表,只需替換 `estimator.py` Layer 1 的權重,契約不變。

---

## 4. 設定配 — 求解器(投影法、確定性)

以**自由配的 100% baseline 為起點**,套保經約束。純函式 `solve(baseline: Allocation, constraints: Constraint[]) -> AllocationResult`。

**演算法**
1. **可行性檢查**:Σ(下限) ≤ 100 ≤ Σ(上限)。不成立 → `feasible=false`,`error` 指出衝突。
2. **鉗制**:每桶夾進 `[下限, 上限]`(`must_include` 視為該桶 floor)。
3. **重分配**:`residual = 100 − Σ(鉗制後)`;把 residual 按 baseline 權重分給「仍有空間」的桶,迭代至收斂(residual≈0 且全在界內)。
4. **回報**:`binding`(被卡住的條件)、`adjustments`(各桶相對 baseline 的位移)、`explanation`(中文一句話)、`needs`(帶回 Layer 1 供追溯)。

**worked example**:baseline A64/B25/C11(= 第 3 節 demo 客戶自由配值),條件「保險下限≥25、金融上限≤60、必含醫療 C≥10」→ A 觸上限降到 60(−4),多出的 4% 按 baseline 權重回流 B、C → ≈ **A60 / B28 / C12**。`explanation`:「金融觸及上限 60%,超出部分回流保險與醫療。」

**本版預設條件清單**(對應原型 4 條):
- 保險佔比下限 `floor / B`
- 必含醫療 / 長照 `must_include / C`
- 金融佔比上限 `cap / A`
- 流動性保留 ≥6個月 `liquidity / null` —— **本版僅顯示,不進三桶計算**

---

## 5. API 契約

```
POST /api/allocation/estimate
  body: ClientInputs
  → 200 { needs: IndependentNeeds, allocation: Allocation }   # Layer 1 + Layer 2 都回

POST /api/allocation/solve
  body: { baseline?: Allocation, client?: ClientInputs, constraints: Constraint[] }
        (未給 baseline 時,先用 client 跑 estimate 得到自由配 baseline)
  → 200 AllocationResult
```

JSON 形狀即第 2 節型別。不可行時仍回 200,以 `feasible=false` + `error` 表達(非 HTTP 錯誤)。

---

## 6. 前端(React/TSX,低樣式耦合)

| 元件 | 角色 |
|---|---|
| `useAllocation()` | 型別化 API client(`estimate()` / `solve()`) |
| `<AllocationStrategy>` | 對應原型「配置策略」整頁(自由配 / 設定配 切換) |
| `<StrategyModeCards>` | 自由配 / 設定配 兩張選擇卡 |
| `<ConstraintEditor>` | 設定配條件輸入(toggle + 數值) |
| `<AllocationResult>` | 甜甜圈 + 長條 + 約束狀態列;可選顯示 Layer 1 個別需求(追溯) |

樣式抽成 CSS 變數 / className,不寫死原型色票,讓同學套自己的 theme。個別需求(Layer 1)預設可折疊顯示,對應教授說的「保經私底下計算」。

---

## 7. 交付結構

```
O/handoff-allocation/
  DESIGN.md          ← 本文件
  README.md          整合指南(怎麼接、契約、範例)
  contract.md        API 契約規格(可單獨給後端)
  backend/
    allocation/
      __init__.py
      models.py       ClientInputs / IndependentNeeds / Allocation / Constraint / AllocationResult
      estimator.py    Layer 1 個別需求 + Layer 2 自由配整合
      solver.py       設定配
      router.py       FastAPI 範例端點
    tests/
      test_estimator.py
      test_solver.py
  frontend/
    types.ts          與 pydantic 對齊
    api.ts            型別化 client
    AllocationStrategy.tsx
    StrategyModeCards.tsx
    ConstraintEditor.tsx
    AllocationResult.tsx
```

整包可直接交付,同學整包拿走整合。

---

## 8. 測試重點

- **Layer 1 個別需求**:三桶各自獨立、**不**被正規化(合計可不等於 100);缺欄位走預設。
- **Layer 2 自由配**:輸出加總=100、demo 客戶數值(A64/B25/C11)。
- **設定配求解器**:尊重下限/上限/必含;不可行偵測(Σ下限>100、必含與上限衝突);重分配後仍在界內且加總=100;binding/adjustments 正確;`needs` 有被帶回。

---

## 9. 後續可調(不阻擋本版整合)

- **達標 / 不達標邏輯**(會議 14:35–15:19):自由配湊到 100% 後若仍達不到客戶目標,系統回頭建議「增加每月投入金額多少」才能達標。本版**不做**,列為下一階段。
- 個別需求(Layer 1)估算常數換成保經真實規則/對照表。
- 流動性保留改成「先扣現金預留、再對剩餘做 ABC」。
- 與同學客戶物件的欄位對映。
- 設定配改最佳化求解器(若約束變複雜)。
