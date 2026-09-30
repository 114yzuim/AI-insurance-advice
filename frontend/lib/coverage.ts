// Coverage facts extracted from each product's own clauses
// (backend product_attributes -> the `coverage` field of /products).
// Products without clause documents have `coverage: null`.

export interface Coverage {
  types: string[];
  is_rider: boolean | null;
  currency: string | null;
  issue_age: { min: number | null; max: number | null } | null;
  coverage_period: string | null;
  payment_terms: string[];
  waiting_periods: { target: string; days: number }[];
  benefit_names: string[];
  exclusion_count: number;
}

export const COVERAGE_LABEL: Record<string, string> = {
  life: "壽險",
  cancer: "癌症",
  critical: "重大疾病",
  accident: "意外",
  daily: "住院日額",
  medical: "實支實付",
  ltc: "長照失能",
};

export const COVERAGE_OPTIONS = Object.entries(COVERAGE_LABEL).map(([value, label]) => ({ value, label }));

/** One-line summary for the AI chat context. */
export function coverageSummary(c: Coverage | null | undefined): string {
  if (!c) return "無條款資料";
  const parts: string[] = [];
  if (c.types.length) parts.push(`保障：${c.types.map((t) => COVERAGE_LABEL[t] ?? t).join("、")}`);
  if (c.is_rider !== null) parts.push(c.is_rider ? "附約" : "主約");
  if (c.issue_age) parts.push(`投保年齡 ${c.issue_age.min ?? "?"}～${c.issue_age.max ?? "?"} 歲`);
  if (c.coverage_period) parts.push(`保險期間：${c.coverage_period}`);
  if (c.waiting_periods.length)
    parts.push(`等待期：${c.waiting_periods.map((w) => `${w.target || "一般"}${w.days}日`).join("、")}`);
  if (c.benefit_names.length) parts.push(`給付項目：${c.benefit_names.join("、")}`);
  if (c.exclusion_count) parts.push(`除外責任 ${c.exclusion_count} 項`);
  return parts.join("；") || "有條款，未擷取到結構化資訊";
}
