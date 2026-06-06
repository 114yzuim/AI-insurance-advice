# API 契約 — 自由配 / 設定配

後端可單獨依此實作;前端 `types.ts` 已與此對齊。JSON 一律 **camelCase**。
所有範例數值皆為實測輸出(demo 客戶:42歲→65退、扶養1、有醫療、風險中)。

## 型別

```ts
ClientInputs {
  age: int                       // 必填
  retireAge: int                 // 必填
  monthlyInvestable?: number = 0
  dependents?: int = 0
  riskTolerance?: "low"|"mid"|"high" = "mid"
  hasMedicalCoverage?: bool = false
  hasLifeCoverage?: bool = false
}

IndependentNeeds { a: number; b: number; c: number }   // Layer 1,各自獨立、不加總 100
Allocation       { a: number; b: number; c: number }   // Layer 2,a+b+c = 100

Constraint {
  id: string
  label: string
  kind: "floor" | "cap" | "must_include" | "liquidity"
  bucket: "A" | "B" | "C" | null
  value: number
  active: bool
}

Adjustment { bucket: "A"|"B"|"C"; baseline: number; final: number; delta: number }

AllocationResult {
  allocation: Allocation
  baseline: Allocation
  needs: IndependentNeeds | null
  feasible: bool
  binding: string[]              // 觸界的 constraint id
  adjustments: Adjustment[]
  explanation: string
  error: string | null
}
```

## 端點

### `POST /api/allocation/estimate` — 自由配(兩層)

Request = `ClientInputs`:
```json
{ "age": 42, "retireAge": 65, "monthlyInvestable": 30000,
  "dependents": 1, "riskTolerance": "mid",
  "hasMedicalCoverage": true, "hasLifeCoverage": true }
```
Response = `{ needs, allocation }`:
```json
{
  "needs": { "a": 53.0, "b": 21.0, "c": 8.8 },
  "allocation": { "a": 64, "b": 25, "c": 11 }
}
```
`needs` 是個別分析層(不加總 100);`allocation` 是整合後的自由配(加總 100)。

### `POST /api/allocation/solve` — 設定配(約束求解)

Request:
```json
{
  "client": { "age": 42, "retireAge": 65, "hasMedicalCoverage": true },
  "constraints": [
    { "id": "ins_floor", "label": "保險佔比下限", "kind": "floor", "bucket": "B", "value": 25, "active": true },
    { "id": "med_must",  "label": "必含醫療 / 長照", "kind": "must_include", "bucket": "C", "value": 10, "active": true },
    { "id": "fin_cap",   "label": "金融佔比上限", "kind": "cap", "bucket": "A", "value": 60, "active": true }
  ]
}
```
> `baseline` 與 `client` 二擇一:給 `baseline`(Allocation)就直接用;只給 `client` 則先自動跑 estimate 取得自由配 baseline。

Response = `AllocationResult`(可行):
```json
{
  "allocation": { "a": 60, "b": 28, "c": 12 },
  "baseline":   { "a": 64, "b": 25, "c": 11 },
  "needs":      { "a": 53.0, "b": 21.0, "c": 8.8 },
  "feasible": true,
  "binding": ["fin_cap"],
  "adjustments": [
    { "bucket": "A", "baseline": 64, "final": 60, "delta": -4 },
    { "bucket": "B", "baseline": 25, "final": 28, "delta": 3 },
    { "bucket": "C", "baseline": 11, "final": 12, "delta": 1 }
  ],
  "explanation": "金融觸及上限 60%;其餘依基準比例重分配。",
  "error": null
}
```

不可行(例:下限總和 > 100%)仍回 **HTTP 200**,以旗標表達:
```json
{ "allocation": {…baseline…}, "baseline": {…}, "needs": null,
  "feasible": false, "binding": [], "adjustments": [],
  "explanation": "", "error": "下限總和 105% 超過 100%（金融≥60%、保險≥25%、醫療≥20%），無可行解。" }
```

## 約束語意

| kind | bucket | 意義 |
|---|---|---|
| `floor` | A/B/C | 該桶下限 `≥ value` |
| `cap` | A/B/C | 該桶上限 `≤ value` |
| `must_include` | 通常 C | 視為該桶 floor(必含、強制 `≥ value`) |
| `liquidity` | `null` | **本版僅顯示,不進三桶計算** |
