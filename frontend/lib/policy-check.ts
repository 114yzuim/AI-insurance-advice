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

export type ClientRiskProfile = {
  age?: number | null;
  monthlyIncome?: number | null;
  monthlyExpense?: number | null;
  occupation?: string | null;
};

export type CoverageTarget = {
  amount: number;
  reason: string;
};

export type CoverageCheck = {
  key: CoverageKey;
  label: string;
  current: number;
  target: number;
  gap: number;
  unit: string;
  status: CheckStatus;
  suggestion: string;
  targetReason: string;
};

export type ClaimReadinessStatus = "ready" | "partial" | "missing";

export type ClaimReadinessItem = {
  key: CoverageKey;
  label: string;
  status: ClaimReadinessStatus;
  reason: string;
  nextStep: string;
};

export type PremiumReview = {
  status: "ok" | "review" | "high" | "unknown";
  label: string;
  message: string;
};

export type PolicyCheckResult = {
  score: number;
  annualPremium: number;
  annualIncome: number;
  premiumRatio: number | null;
  policyCount: number;
  companyCount: number;
  incompleteCount: number;
  checks: CoverageCheck[];
  warnings: string[];
  priorities: CoverageCheck[];
  targetBasis: string[];
  claimReadiness: ClaimReadinessItem[];
  duplicateWarnings: string[];
  premiumReview: PremiumReview;
};

export const DEFAULT_COVERAGE_TARGETS: Record<CoverageKey, CoverageTarget> = {
  life: { amount: 1000, reason: "未提供收入時，先以一般家庭責任基準估算。" },
  cancer: { amount: 300, reason: "癌症一次金以 300 萬作為初步檢視基準。" },
  critical: { amount: 200, reason: "重大傷病以 200 萬作為醫療與收入中斷緩衝。" },
  accident: { amount: 500, reason: "意外保障以 500 萬作為基本風險承接。" },
  daily: { amount: 3000, reason: "住院日額以每日 3,000 元作為基本住院支出補貼。" },
  medical: { amount: 20, reason: "實支實付以 20 萬作為初步雜費額度基準。" },
  ltc: { amount: 5, reason: "長照給付以每月 5 萬作為基本照護現金流。" },
};

const SUGGESTIONS: Record<CoverageKey, string> = {
  life: "壽險保障主要承接家庭責任、房貸、負債與未成年子女照顧責任。",
  cancer: "癌症保障建議確認一次給付額度，避免只有療程型或日額型保障。",
  critical: "重大傷病保障可補足重大疾病初期的收入中斷與自費醫療壓力。",
  accident: "意外保障需搭配職業風險、通勤型態與家庭責任檢視。",
  daily: "住院日額可作為住院期間固定支出的補償，但不應取代實支實付。",
  medical: "實支實付是理賠服務最常用的核心資料，需確認額度、雜費與手術限制。",
  ltc: "長照保障需確認每月給付金額與啟動條件，避免只看保額不看條款。",
};

function roundTo(value: number, unit: number) {
  return Math.max(0, Math.round(value / unit) * unit);
}

function getAnnualIncome(profile: ClientRiskProfile) {
  return Number(profile.monthlyIncome || 0) * 12;
}

function isHigherRiskOccupation(occupation?: string | null) {
  if (!occupation) return false;
  return ["工地", "工程", "司機", "外送", "機械", "消防", "警察", "高空", "業務"].some((keyword) =>
    occupation.includes(keyword),
  );
}

export function buildCoverageTargets(profile: ClientRiskProfile = {}): Record<CoverageKey, CoverageTarget> {
  const age = Number(profile.age || 0);
  const annualIncome = getAnnualIncome(profile);
  const hasIncome = annualIncome > 0;
  const highRiskJob = isHigherRiskOccupation(profile.occupation);
  const lifeMultiplier = age >= 55 ? 5 : age >= 45 ? 8 : 10;
  const incomeInWan = annualIncome / 10000;

  const lifeTarget = hasIncome ? Math.max(500, roundTo(incomeInWan * lifeMultiplier, 50)) : DEFAULT_COVERAGE_TARGETS.life.amount;
  const criticalTarget = hasIncome ? Math.max(200, roundTo(incomeInWan * 2, 50)) : DEFAULT_COVERAGE_TARGETS.critical.amount;
  const accidentTarget = hasIncome
    ? Math.max(highRiskJob ? 800 : 500, roundTo(incomeInWan * (highRiskJob ? 8 : 5), 50))
    : highRiskJob
      ? 800
      : DEFAULT_COVERAGE_TARGETS.accident.amount;
  const dailyTarget = age >= 55 ? 4000 : age >= 40 ? 3500 : DEFAULT_COVERAGE_TARGETS.daily.amount;
  const medicalTarget = age >= 55 ? 30 : DEFAULT_COVERAGE_TARGETS.medical.amount;
  const cancerTarget = age >= 45 ? 300 : 200;
  const ltcTarget = age >= 50 ? 6 : DEFAULT_COVERAGE_TARGETS.ltc.amount;

  return {
    life: {
      amount: lifeTarget,
      reason: hasIncome
        ? `以年收入 ${formatMoney(annualIncome)} 的 ${lifeMultiplier} 倍估算家庭責任。`
        : DEFAULT_COVERAGE_TARGETS.life.reason,
    },
    cancer: {
      amount: cancerTarget,
      reason: age >= 45 ? "45 歲以上先以 300 萬癌症一次金檢視。" : "45 歲以下先以 200 萬癌症一次金檢視。",
    },
    critical: {
      amount: criticalTarget,
      reason: hasIncome ? "以約 2 年收入作為重大傷病初期現金流緩衝。" : DEFAULT_COVERAGE_TARGETS.critical.reason,
    },
    accident: {
      amount: accidentTarget,
      reason: highRiskJob ? "職業風險較高，意外保障基準提高。" : DEFAULT_COVERAGE_TARGETS.accident.reason,
    },
    daily: {
      amount: dailyTarget,
      reason: age >= 40 ? "年齡提高後，住院期間固定支出風險同步提高。" : DEFAULT_COVERAGE_TARGETS.daily.reason,
    },
    medical: {
      amount: medicalTarget,
      reason: age >= 55 ? "55 歲以上建議提高實支實付雜費檢視基準。" : DEFAULT_COVERAGE_TARGETS.medical.reason,
    },
    ltc: {
      amount: ltcTarget,
      reason: age >= 50 ? "50 歲以上先提高長照現金流檢視基準。" : DEFAULT_COVERAGE_TARGETS.ltc.reason,
    },
  };
}

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

function buildClaimReadiness(checks: CoverageCheck[], incompleteCount: number): ClaimReadinessItem[] {
  const claimCoreKeys: CoverageKey[] = ["medical", "daily", "accident", "cancer", "critical", "ltc"];

  return claimCoreKeys.map((key) => {
    const check = checks.find((item) => item.key === key);
    const hasCoverage = Number(check?.current || 0) > 0;
    const label = check?.label || COVERAGE_LABELS[key].label;

    if (!hasCoverage) {
      return {
        key,
        label,
        status: "missing",
        reason: "目前未看到可用保障，發生事故時可能無法進入自動比對。",
        nextStep: "先確認是否有紙本保單、附約或舊保單尚未輸入。",
      };
    }

    if (incompleteCount > 0) {
      return {
        key,
        label,
        status: "partial",
        reason: "已有保障額度，但部分保單缺少條款、保費、保單號或保障明細。",
        nextStep: "補齊缺漏資料後，再用診斷書、收據與醫療明細做理賠比對。",
      };
    }

    return {
      key,
      label,
      status: "ready",
      reason: "已有可比對的保障資料，可作為理賠服務前置資料。",
      nextStep: "發生理賠時上傳診斷證明、收據與醫療費用明細。",
    };
  });
}

function buildDuplicateWarnings(checks: CoverageCheck[]) {
  return checks
    .filter((check) => check.target > 0 && check.current >= check.target * 1.5)
    .map((check) => `${check.label}現有保障約為建議基準的 ${Math.round((check.current / check.target) * 100)}%，建議檢查是否有重複投保、保費效率或條款重疊。`);
}

function buildPremiumReview(premiumRatio: number | null, annualPremium: number): PremiumReview {
  if (annualPremium <= 0) {
    return {
      status: "unknown",
      label: "保費資料待補",
      message: "尚未取得年繳保費，無法判斷保費是否過高或是否有重複支出。",
    };
  }
  if (premiumRatio === null) {
    return {
      status: "unknown",
      label: "收入資料待補",
      message: `目前年繳保費為 ${formatMoney(annualPremium)}，請補上收入後再判斷保費收入比。`,
    };
  }
  if (premiumRatio > 0.15) {
    return {
      status: "high",
      label: "保費壓力偏高",
      message: `年繳保費約占年收入 ${Math.round(premiumRatio * 100)}%，建議優先檢查重複保障、儲蓄型保單占比與可調整附約。`,
    };
  }
  if (premiumRatio > 0.1) {
    return {
      status: "review",
      label: "建議檢查保費效率",
      message: `年繳保費約占年收入 ${Math.round(premiumRatio * 100)}%，可進一步確認保障是否集中在醫療、失能、重大傷病等高用途項目。`,
    };
  }
  return {
    status: "ok",
    label: "保費比例可接受",
    message: `年繳保費約占年收入 ${Math.round(premiumRatio * 100)}%，下一步可聚焦保障缺口與理賠可用性。`,
  };
}

export function analyzePolicyCheck(
  policies: Policy[],
  profile: ClientRiskProfile = {},
  targets = buildCoverageTargets(profile),
): PolicyCheckResult {
  const summary = getPolicySummary(policies);
  const annualIncome = getAnnualIncome(profile);
  const checks = COVERAGE_ORDER.map((key) => {
    const current = Number(summary.coverage[key] || 0);
    const target = targets[key].amount;
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
      targetReason: targets[key].reason,
    };
  });
  const premiumRatio = annualIncome > 0 ? summary.premium / annualIncome : null;
  const claimReadiness = buildClaimReadiness(checks, summary.incomplete);
  const duplicateWarnings = buildDuplicateWarnings(checks);
  const premiumReview = buildPremiumReview(premiumRatio, summary.premium);

  const warnings = [
    ...(summary.policyCount === 0 ? ["尚未輸入現有保單，無法進行有效健診。"] : []),
    ...(summary.incomplete > 0 ? [`有 ${summary.incomplete} 張保單資料待補，健診結果需等資料補齊後再確認。`] : []),
    ...(annualIncome <= 0 ? ["客戶收入尚未建立，目前建議額度採用一般基準，精準度有限。"] : []),
    ...(premiumRatio !== null && premiumRatio > 0.15
      ? [`年繳保費約占年收入 ${Math.round(premiumRatio * 100)}%，建議檢查是否有重複保障或保費壓力。`]
      : []),
    ...(summary.premium > 0 && summary.policyCount > 0
      ? [`目前年繳保費為 ${formatMoney(summary.premium)}，需搭配家庭責任與現金流確認是否合理。`]
      : []),
  ];

  return {
    score: getScore(checks, summary.incomplete),
    annualPremium: summary.premium,
    annualIncome,
    premiumRatio,
    policyCount: summary.policyCount,
    companyCount: summary.companyCount,
    incompleteCount: summary.incomplete,
    checks,
    warnings,
    priorities: checks
      .filter((check) => check.status !== "ok")
      .sort((a, b) => b.gap - a.gap)
      .slice(0, 3),
    targetBasis: [
      annualIncome > 0 ? `年收入：${formatMoney(annualIncome)}` : "年收入：待補，採一般基準",
      profile.age ? `年齡：${profile.age} 歲` : "年齡：待補",
      profile.occupation ? `職業：${profile.occupation}` : "職業：待補",
    ],
    claimReadiness,
    duplicateWarnings,
    premiumReview,
  };
}

export function formatCheckValue(check: Pick<CoverageCheck, "key" | "current">) {
  return formatCoverage(check.key, check.current);
}

export function formatGapValue(check: Pick<CoverageCheck, "key" | "gap">) {
  return formatCoverage(check.key, check.gap);
}
