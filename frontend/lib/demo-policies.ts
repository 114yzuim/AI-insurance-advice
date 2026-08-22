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
  coverages: Partial<Record<CoverageKey, number>>;
  riders: string[];
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
  coverage: Record<CoverageKey, number>;
};

export type PolicyPortfolio = {
  profile?: {
    id: string;
    owner_name?: string;
    relation?: string;
    policy_count?: number;
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
  return {
    policyCount: policies.length,
    companyCount: new Set(policies.map((policy) => policy.company).filter(Boolean)).size,
    premium: policies.reduce((sum, policy) => sum + (Number(policy.annualPremium) || 0), 0),
    incomplete: policies.filter((policy) => policy.status === "待補資料").length,
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
    coverages: (raw.coverages ?? {}) as Partial<Record<CoverageKey, number>>,
    riders: Array.isArray(raw.riders) ? raw.riders.map(String) : [],
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
