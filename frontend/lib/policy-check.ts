import {
  COVERAGE_LABELS,
  COVERAGE_ORDER,
  formatCoverage,
  formatMoney,
  getPolicySummary,
  type CoverageKey,
  type Policy,
} from "@/lib/demo-policies";

export type CheckStatus = "missing" | "gap" | "ok";

export type CoverageCheck = {
  key: CoverageKey;
  label: string;
  current: number;
  target: number;
  gap: number;
  unit: string;
  status: CheckStatus;
  suggestion: string;
};

export type PolicyCheckResult = {
  score: number;
  annualPremium: number;
  policyCount: number;
  companyCount: number;
  incompleteCount: number;
  checks: CoverageCheck[];
  warnings: string[];
  priorities: CoverageCheck[];
};

export const DEFAULT_COVERAGE_TARGETS: Record<CoverageKey, number> = {
  life: 1000,
  cancer: 300,
  critical: 200,
  accident: 500,
  daily: 3000,
  medical: 20,
  ltc: 5,
};

const SUGGESTIONS: Record<CoverageKey, string> = {
  life: "壽險保障主要用來承接家庭責任、房貸與未成年子女照顧責任。",
  cancer: "癌症保障建議確認一次給付額度，避免只剩療程型保障。",
  critical: "重大傷病保障可補足重大疾病初期的收入中斷與自費醫療壓力。",
  accident: "意外保障需搭配職業風險與通勤型態檢視。",
  daily: "住院日額可作為住院期間固定支出的補償，但不應取代實支實付。",
  medical: "實支實付是理賠服務最常用的核心資料，需確認額度、雜費與手術限制。",
  ltc: "長照保障需確認每月給付金額與啟動條件，避免只看保額不看條款。",
};

function getStatus(current: number, target: number): CheckStatus {
  if (current <= 0) return "missing";
  if (current < target) return "gap";
  return "ok";
}

function getScore(checks: CoverageCheck[], incompleteCount: number) {
  if (checks.length === 0) return 0;
  const statusScore = checks.reduce((sum, check) => {
    if (check.status === "ok") return sum + 100;
    if (check.status === "gap") return sum + Math.max(35, Math.round((check.current / check.target) * 100));
    return sum;
  }, 0);
  const penalty = incompleteCount * 4;
  return Math.max(0, Math.min(100, Math.round(statusScore / checks.length) - penalty));
}

export function analyzePolicyCheck(policies: Policy[], targets = DEFAULT_COVERAGE_TARGETS): PolicyCheckResult {
  const summary = getPolicySummary(policies);
  const checks = COVERAGE_ORDER.map((key) => {
    const current = Number(summary.coverage[key] || 0);
    const target = targets[key];
    const gap = Math.max(target - current, 0);
    const status = getStatus(current, target);

    return {
      key,
      label: COVERAGE_LABELS[key].label,
      current,
      target,
      gap,
      unit: COVERAGE_LABELS[key].unit,
      status,
      suggestion: SUGGESTIONS[key],
    };
  });

  const warnings = [
    ...(summary.policyCount === 0 ? ["尚未輸入現有保單，無法進行有效健診。"] : []),
    ...(summary.incomplete > 0 ? [`有 ${summary.incomplete} 張保單資料待補，健診結果需等資料補齊後再確認。`] : []),
    ...(summary.premium > 0 && summary.policyCount > 0
      ? [`目前年繳保費為 ${formatMoney(summary.premium)}，需搭配收入與家庭責任判斷是否合理。`]
      : []),
  ];

  return {
    score: getScore(checks, summary.incomplete),
    annualPremium: summary.premium,
    policyCount: summary.policyCount,
    companyCount: summary.companyCount,
    incompleteCount: summary.incomplete,
    checks,
    warnings,
    priorities: checks
      .filter((check) => check.status !== "ok")
      .sort((a, b) => b.gap - a.gap)
      .slice(0, 3),
  };
}

export function formatCheckValue(check: Pick<CoverageCheck, "key" | "current">) {
  return formatCoverage(check.key, check.current);
}

export function formatGapValue(check: Pick<CoverageCheck, "key" | "gap">) {
  return formatCoverage(check.key, check.gap);
}
