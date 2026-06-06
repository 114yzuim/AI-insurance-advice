# 自由配 / 設定配 — 配置模組(交付包)

把「保經 Planning Studio」的兩個核心概念做成自包含模組,給 **React/TSX 前端 + Python 後端** 的系統直接整合。

- **自由配（Free Allocation）** — 系統依客戶資產/年期/需求,先**各自獨立純算** A/B/C(個別分析層),再整合成**加總 100%** 的配置。
- **設定配（Constrained Allocation）** — 保經先設條件(保險下限、必含醫療、金融上限…),系統在約束內求解,一樣輸出 100%。

> 設計依據與決策見 [`DESIGN.md`](./DESIGN.md);API 細節見 [`contract.md`](./contract.md)。
> 兩層模型(個別獨立 → 湊 100%)是依 2026-05-01 與邱昭彰教授的會議定調。

---

## 目錄

```
handoff-allocation/
├── DESIGN.md            設計 spec
├── contract.md          API 契約
├── backend/             Python(估算 + 求解 + FastAPI router + 測試)
│   ├── allocation/      models / estimator / solver / router
│   └── tests/           pytest(16 項,全綠)
└── frontend/            React/TSX(型別 / API client / 4 元件 / 樣式)
```

---

## 後端整合

```bash
cd backend
pip install -r requirements.txt   # pydantic(必要)、fastapi(只有 router 需要)
pytest                            # 16 passed
```

掛上 router:
```python
from fastapi import FastAPI
from allocation.router import router

app = FastAPI()
app.include_router(router)        # 提供 /api/allocation/estimate、/solve
```

也可不透過 HTTP,直接呼叫純函式:
```python
from allocation import estimate, solve, default_constraints, ClientInputs

needs, baseline = estimate(ClientInputs(age=42, retire_age=65,
                                        dependents=1, has_medical_coverage=True))
# needs = a53/b21/c8.8(個別,不加總) ; baseline = a64/b25/c11(自由配,加總100)

result = solve(baseline, default_constraints())
# result.allocation = a60/b28/c12 ; result.explanation = "金融觸及上限 60%;…"
```

---

## 前端整合

把 `frontend/` 的檔案放進你的專案(需要 React 18 + TypeScript)。

```tsx
import { AllocationStrategy } from "./allocation/AllocationStrategy";
import "./allocation/styles.css";            // 可選的中性預設樣式

<AllocationStrategy
  client={{ age: 42, retireAge: 65, dependents: 1, hasMedicalCoverage: true }}
  baseUrl="/api/allocation"                  // 或傳 api={yourAllocationApi}
  onNext={(view) => goToScenarioCompare(view)}
/>
```

- 切「自由配」→ 自動打 `estimate`;切「設定配」→ 顯示條件編輯器,改條件即時打 `solve`。
- `frontend/types.ts` 與後端 pydantic 模型欄位對齊;`tsconfig.json` 已附,`strict` 下型別檢查通過。
- 樣式全走 CSS 變數(`--alloc-a/b/c`、`--alloc-surface`…),改 `:root` 即可套你的 theme,不必動元件。

元件:`AllocationStrategy`(整頁)、`StrategyModeCards`(模式卡)、`ConstraintEditor`(條件)、`AllocationResult`(甜甜圈+長條+約束狀態+可折疊的個別分析)。

---

## 客製點

| 想改什麼 | 改哪裡 |
|---|---|
| 個別需求估算規則(換成保經真實邏輯/對照表) | `backend/allocation/estimator.py` 的 `individual_needs()` |
| 設定配預設條件清單 | `backend/allocation/__init__.py` 的 `default_constraints()` / 前端 `types.ts` 的 `DEFAULT_CONSTRAINTS` |
| 配色 / 字體 | `frontend/styles.css` 的 `:root` 變數 |
| 客戶欄位對映到你的系統 | `ClientInputs`(`models.py` + `types.ts`) |

---

## 本版範圍

**已含**:兩層估算、約束求解(含不可行偵測)、API、TSX 元件、樣式、後端測試。

**後續(刻意不做,見 DESIGN.md §9)**:
- **達標 / 不達標** → 湊到 100% 仍達不到客戶目標時,建議「增加每月投入金額」。
- 流動性保留納入三桶計算(目前僅顯示)。
- 設定配改用最佳化求解器(若約束變更複雜)。
