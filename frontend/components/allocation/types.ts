// 與後端 pydantic 模型對齊的 TS 型別(JSON 走 camelCase)。
// 對應 backend/allocation/models.py

export type RiskTolerance = "low" | "mid" | "high";
export type Bucket = "A" | "B" | "C";
export type ConstraintKind = "floor" | "cap" | "must_include" | "liquidity";

export interface ClientInputs {
  age: number;
  retireAge: number;
  monthlyInvestable?: number;
  dependents?: number;
  riskTolerance?: RiskTolerance;
  hasMedicalCoverage?: boolean;
  hasLifeCoverage?: boolean;
}

/** Layer 1 / 個別分析:各自獨立、不加總 100。 */
export interface IndependentNeeds {
  a: number;
  b: number;
  c: number;
}

/** Layer 2:配置比例,a + b + c = 100。 */
export interface Allocation {
  a: number;
  b: number;
  c: number;
}

export interface Constraint {
  id: string;
  label: string;
  kind: ConstraintKind;
  bucket: Bucket | null;
  value: number;
  active: boolean;
}

export interface Adjustment {
  bucket: Bucket;
  baseline: number;
  final: number;
  delta: number;
}

export interface AllocationResult {
  allocation: Allocation;
  baseline: Allocation;
  needs?: IndependentNeeds | null;
  feasible: boolean;
  binding: string[];
  adjustments: Adjustment[];
  explanation: string;
  error?: string | null;
}

export interface EstimateResponse {
  needs: IndependentNeeds;
  allocation: Allocation;
}

export interface SolveRequest {
  baseline?: Allocation | null;
  client?: ClientInputs | null;
  constraints: Constraint[];
}

export type StrategyMode = "free" | "cons";

/** 三桶顯示用 metadata;顏色走 CSS 變數,方便換 theme。 */
export const BUCKET_META: Record<Bucket, { label: string; sub: string; cssVar: string }> = {
  A: { label: "金融 / 投資", sub: "ETF、債券、定存等資產累積", cssVar: "var(--alloc-a, #4a6fa5)" },
  B: { label: "保險 / 年金", sub: "儲蓄險、年金、投資型保單", cssVar: "var(--alloc-b, #5b8c6e)" },
  C: { label: "醫療 / 長照", sub: "醫療險、失能、長照給付", cssVar: "var(--alloc-c, #6faaa0)" },
};

/** 對應 backend default_constraints() — 原型「設定配」預設 4 條。 */
export const DEFAULT_CONSTRAINTS: Constraint[] = [
  { id: "ins_floor", label: "保險購買佔比", kind: "floor", bucket: "B", value: 25, active: true },
  { id: "med_must", label: "醫療/長照 投入資源", kind: "must_include", bucket: "C", value: 10, active: true },
  { id: "fin_cap", label: "金融投資增值", kind: "cap", bucket: "A", value: 60, active: true },
  { id: "liquidity", label: "流動性保留 ≥6個月", kind: "liquidity", bucket: null, value: 6, active: false },
];
