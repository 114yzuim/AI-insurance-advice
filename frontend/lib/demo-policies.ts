export type CoverageKey = "life" | "cancer" | "critical" | "accident" | "daily" | "medical" | "ltc";

export type Policy = {
  id: string;
  company: string;
  name: string;
  policyNo: string;
  role: string;
  status: string;
  annualPremium: number;
  effectiveDate: string;
  productId?: string;
  sourceDocumentId?: number | null;
  coverages: Partial<Record<CoverageKey, number>>;
  riders: string[];
  completeness?: PolicyCompleteness;
};

export type PolicyCompleteness = {
  score: number;
  level: "complete" | "partial" | "insufficient";
  label: string;
  missing: Array<{ key: string; label: string }>;
  missing_count: number;
  total_checks: number;
};

export type CoverageMeta = {
  label: string;
  unit: string;
};

export type PolicySummary = {
  policyCount: number;
  companyCount: number;
  premium: number;
  incomplete: number;
  averageCompleteness: number;
  coverage: Record<CoverageKey, number>;
};

export type PolicyPortfolio = {
  profile?: {
    id: string;
    owner_name?: string;
    relation?: string;
    policy_count?: number;
    incomplete_policy_count?: number;
    average_completeness?: number;
  } | null;
  policies: Policy[];
  summary: PolicySummary;
};

export type InsuranceProfile = NonNullable<PolicyPortfolio["profile"]>;

export const COVERAGE_ORDER: CoverageKey[] = ["life", "cancer", "critical", "accident", "daily", "medical", "ltc"];

export const COVERAGE_LABELS: Record<CoverageKey, CoverageMeta> = {
  life: { label: "壽險保障", unit: "萬" },
  cancer: { label: "癌症保障", unit: "萬" },
  critical: { label: "重大傷病", unit: "萬" },
  accident: { label: "意外保障", unit: "萬" },
  daily: { label: "住院日額", unit: "元" },
  medical: { label: "實支實付", unit: "萬" },
  ltc: { label: "長照保障", unit: "萬/月" },
};

export const DEMO_POLICIES: Policy[] = [];

export function getCoverageTotals(policies: Policy[] = []): Record<CoverageKey, number> {
  return COVERAGE_ORDER.reduce((acc, key) => {
    acc[key] = policies.reduce((sum, policy) => sum + (Number(policy.coverages[key]) || 0), 0);
    return acc;
  }, {} as Record<CoverageKey, number>);
}

export function getPolicySummary(policies: Policy[] = []): PolicySummary {
  const completenessScores = policies.map((policy) => getPolicyCompleteness(policy).score);
  return {
    policyCount: policies.length,
    companyCount: new Set(policies.map((policy) => policy.company).filter(Boolean)).size,
    premium: policies.reduce((sum, policy) => sum + (Number(policy.annualPremium) || 0), 0),
    incomplete: policies.filter((policy) => getPolicyCompleteness(policy).missing_count > 0).length,
    averageCompleteness: completenessScores.length
      ? Math.round(completenessScores.reduce((sum, score) => sum + score, 0) / completenessScores.length)
      : 0,
    coverage: getCoverageTotals(policies),
  };
}

export function normalizePolicy(raw: Record<string, unknown>): Policy {
  return {
    id: String(raw.id ?? ""),
    company: String(raw.company_name ?? raw.company ?? ""),
    name: String(raw.policy_name ?? raw.name ?? ""),
    policyNo: String(raw.policy_no ?? raw.policyNo ?? ""),
    role: String(raw.role ?? "主約"),
    status: String(raw.status ?? "有效"),
    annualPremium: Number(raw.annual_premium ?? raw.annualPremium ?? 0),
    effectiveDate: String(raw.effective_date ?? raw.effectiveDate ?? ""),
    productId: String(raw.product_id ?? raw.productId ?? ""),
    sourceDocumentId: raw.source_document_id || raw.sourceDocumentId ? Number(raw.source_document_id ?? raw.sourceDocumentId) : null,
    coverages: (raw.coverages ?? {}) as Partial<Record<CoverageKey, number>>,
    riders: Array.isArray(raw.riders) ? raw.riders.map(String) : [],
    completeness: normalizeCompleteness(raw.completeness),
  };
}

export function normalizeCompleteness(raw: unknown): PolicyCompleteness | undefined {
  if (!raw || typeof raw !== "object") return undefined;
  const data = raw as Partial<PolicyCompleteness>;
  return {
    score: Number(data.score ?? 0),
    level: data.level ?? "insufficient",
    label: String(data.label ?? "資料不足"),
    missing: Array.isArray(data.missing)
      ? data.missing.map((item) => ({
          key: String((item as { key?: unknown }).key ?? ""),
          label: String((item as { label?: unknown }).label ?? ""),
        }))
      : [],
    missing_count: Number(data.missing_count ?? 0),
    total_checks: Number(data.total_checks ?? 0),
  };
}

export function getPolicyCompleteness(policy: Policy): PolicyCompleteness {
  if (policy.completeness) return policy.completeness;
  const checks = [
    { key: "company", label: "保險公司", ok: Boolean(policy.company && policy.company !== "未知保險公司") },
    { key: "name", label: "商品 / 保單名稱", ok: Boolean(policy.name && !policy.name.includes("待 OCR")) },
    { key: "policyNo", label: "保單號碼", ok: Boolean(policy.policyNo) },
    { key: "role", label: "主約 / 附約", ok: Boolean(policy.role) },
    { key: "status", label: "保單狀態", ok: Boolean(policy.status && policy.status !== "待補資料") },
    { key: "annualPremium", label: "年繳保費", ok: Number(policy.annualPremium || 0) > 0 },
    { key: "effectiveDate", label: "生效日 / 保單期間", ok: Boolean(policy.effectiveDate) },
    { key: "coverages", label: "保障額度", ok: Object.values(policy.coverages).some((amount) => Number(amount || 0) > 0) },
    { key: "termsSource", label: "條款 / 來源商品", ok: Boolean(policy.productId || policy.sourceDocumentId) },
  ];
  const missing = checks.filter((item) => !item.ok).map(({ key, label }) => ({ key, label }));
  const score = checks.length ? Math.round(((checks.length - missing.length) / checks.length) * 100) : 0;
  return {
    score,
    level: score >= 90 ? "complete" : score >= 65 ? "partial" : "insufficient",
    label: score >= 90 ? "可直接健診" : score >= 65 ? "仍待補強" : "資料不足",
    missing,
    missing_count: missing.length,
    total_checks: checks.length,
  };
}

export function normalizePolicyPortfolio(raw: Record<string, unknown>): PolicyPortfolio {
  const policies = Array.isArray(raw.policies)
    ? raw.policies.map((policy) => normalizePolicy(policy as Record<string, unknown>))
    : [];
  const calculatedSummary = getPolicySummary(policies);
  const rawSummary = raw.summary && typeof raw.summary === "object" ? (raw.summary as Partial<PolicySummary>) : {};

  return {
    profile: (raw.profile as PolicyPortfolio["profile"]) ?? null,
    policies,
    summary: {
      ...calculatedSummary,
      ...rawSummary,
      coverage: {
        ...calculatedSummary.coverage,
        ...(rawSummary.coverage ?? {}),
      },
    },
  };
}

export async function fetchPolicyPortfolio(profileId = "demo-user"): Promise<PolicyPortfolio> {
  const res = await fetch(`/api/policies?profile_id=${encodeURIComponent(profileId)}`, { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load policies");
  return normalizePolicyPortfolio(await res.json());
}

export async function fetchInsuranceProfiles(): Promise<InsuranceProfile[]> {
  const res = await fetch("/api/policies/profiles", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load profiles");
  return res.json();
}

export function getPoliciesByCompany(policies: Policy[] = []) {
  const groups = policies.reduce((acc, policy) => {
    const company = policy.company || "未知保險公司";
    acc[company] = acc[company] ?? [];
    acc[company].push(policy);
    return acc;
  }, {} as Record<string, Policy[]>);

  return Object.entries(groups).map(([company, companyPolicies]) => ({
    company,
    policies: companyPolicies,
    annualPremium: companyPolicies.reduce((sum, policy) => sum + (Number(policy.annualPremium) || 0), 0),
  }));
}

export function formatMoney(value: number) {
  return `NT$ ${Number(value || 0).toLocaleString("zh-TW")}`;
}

export function formatCoverage(key: CoverageKey, value: number) {
  const meta = COVERAGE_LABELS[key];
  return `${Number(value || 0).toLocaleString("zh-TW")} ${meta.unit}`;
}

export function formatPolicyContextForAi(policies: Policy[] = []) {
  const summary = getPolicySummary(policies);

  if (summary.policyCount === 0) {
    return "目前系統沒有可用的個人保單資料。回答時請先提醒使用者建立或上傳保單，不要假設已有保障。";
  }

  const coverageLines = COVERAGE_ORDER.map((key) => {
    return `- ${COVERAGE_LABELS[key].label}: ${formatCoverage(key, summary.coverage[key])}`;
  }).join("\n");

  const policyLines = policies.map((policy, index) => {
    const coverages = COVERAGE_ORDER
      .filter((key) => policy.coverages[key])
      .map((key) => `${COVERAGE_LABELS[key].label} ${formatCoverage(key, policy.coverages[key] ?? 0)}`)
      .join("、");
    return `${index + 1}. ${policy.company} / ${policy.name} / ${policy.role} / ${policy.status} / 年繳保費 ${policy.annualPremium.toLocaleString("zh-TW")} 元 / ${coverages || "保障資料待補"}`;
  }).join("\n");

  return `目前系統中的個人保單共有 ${summary.policyCount} 張，橫跨 ${summary.companyCount} 家保險公司，年繳保費 ${summary.premium.toLocaleString("zh-TW")} 元。

保障總覽:
${coverageLines}

保單明細:
${policyLines}

回答規則:
- 優先根據上述個人保單資料回答。
- 若保單資料不足，請明確指出缺少哪些資料。
- 不要假設使用者有系統中不存在的保障。`;
}
