export type CoverageKey =
  | "life"
  | "cancer"
  | "critical"
  | "accident"
  | "daily"
  | "medical"
  | "ltc";

export type Policy = {
  id: string;
  company: string;
  name: string;
  policyNo: string;
  role: "主約" | "附約";
  status: "有效" | "待補資料";
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
  ltc: { label: "長照保障", unit: "萬元/月" },
};

export const DEMO_POLICIES: Policy[] = [
  {
    id: "ct-life-001",
    company: "國泰人壽",
    name: "新守護終身壽險",
    policyNo: "CT-2020-0188",
    role: "主約",
    status: "有效",
    annualPremium: 42000,
    effectiveDate: "2020/08/15",
    coverages: { life: 500, accident: 300 },
    riders: ["新真全意住院醫療", "好骨力傷害醫療"],
  },
  {
    id: "ct-med-002",
    company: "國泰人壽",
    name: "新真全意住院醫療健康保險附約",
    policyNo: "CT-2020-HS2",
    role: "附約",
    status: "有效",
    annualPremium: 18500,
    effectiveDate: "2020/08/15",
    coverages: { daily: 2000, medical: 20 },
    riders: [],
  },
  {
    id: "fb-life-001",
    company: "富邦人壽",
    name: "安心定期壽險",
    policyNo: "FB-2019-6621",
    role: "主約",
    status: "有效",
    annualPremium: 28000,
    effectiveDate: "2019/11/02",
    coverages: { life: 700, critical: 100 },
    riders: ["防癌一次給付健康保險附約"],
  },
  {
    id: "fb-cancer-002",
    company: "富邦人壽",
    name: "防癌一次給付健康保險附約",
    policyNo: "FB-2019-CA1",
    role: "附約",
    status: "有效",
    annualPremium: 21500,
    effectiveDate: "2019/11/02",
    coverages: { cancer: 200 },
    riders: [],
  },
  {
    id: "gl-critical-001",
    company: "全球人壽",
    name: "醫卡照重大傷病健康保險",
    policyNo: "GL-2021-3107",
    role: "主約",
    status: "有效",
    annualPremium: 23800,
    effectiveDate: "2021/04/20",
    coverages: { critical: 100, cancer: 100 },
    riders: [],
  },
  {
    id: "sk-acc-001",
    company: "新光人壽",
    name: "意外傷害保險附約",
    policyNo: "SK-2018-7789",
    role: "附約",
    status: "待補資料",
    annualPremium: 6200,
    effectiveDate: "2018/06/01",
    coverages: { accident: 700 },
    riders: [],
  },
  {
    id: "tw-med-001",
    company: "台灣人壽",
    name: "住院醫療健康保險附約",
    policyNo: "TW-2022-0912",
    role: "附約",
    status: "有效",
    annualPremium: 16800,
    effectiveDate: "2022/09/12",
    coverages: { daily: 3000, medical: 20 },
    riders: [],
  },
  {
    id: "kgi-ltc-001",
    company: "凱基人壽",
    name: "長期照顧終身健康保險",
    policyNo: "KGI-2023-1120",
    role: "主約",
    status: "有效",
    annualPremium: 11200,
    effectiveDate: "2023/01/05",
    coverages: { ltc: 5 },
    riders: [],
  },
];

export function getCoverageTotals(policies: Policy[] = DEMO_POLICIES): Record<CoverageKey, number> {
  return COVERAGE_ORDER.reduce((acc, key) => {
    acc[key] = policies.reduce((sum, policy) => sum + (policy.coverages[key] ?? 0), 0);
    return acc;
  }, {} as Record<CoverageKey, number>);
}

export function getPolicySummary(policies: Policy[] = DEMO_POLICIES) {
  return {
    policyCount: policies.length,
    companyCount: new Set(policies.map((p) => p.company)).size,
    premium: policies.reduce((sum, policy) => sum + policy.annualPremium, 0),
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
    role: (raw.role === "附約" ? "附約" : "主約") as Policy["role"],
    status: (raw.status === "待補資料" ? "待補資料" : "有效") as Policy["status"],
    annualPremium: Number(raw.annual_premium ?? raw.annualPremium ?? 0),
    effectiveDate: String(raw.effective_date ?? raw.effectiveDate ?? ""),
    coverages: (raw.coverages ?? {}) as Partial<Record<CoverageKey, number>>,
    riders: Array.isArray(raw.riders) ? raw.riders.map(String) : [],
  };
}

export function normalizePolicyPortfolio(raw: Record<string, unknown>): PolicyPortfolio {
  const policies = Array.isArray(raw.policies)
    ? raw.policies.map((policy) => normalizePolicy(policy as Record<string, unknown>))
    : DEMO_POLICIES;
  const summary = raw.summary && typeof raw.summary === "object"
    ? {
        ...getPolicySummary(policies),
        ...(raw.summary as Partial<PolicySummary>),
        coverage: {
          ...getCoverageTotals(policies),
          ...((raw.summary as { coverage?: Partial<Record<CoverageKey, number>> }).coverage ?? {}),
        },
      }
    : getPolicySummary(policies);
  return {
    profile: (raw.profile as PolicyPortfolio["profile"]) ?? null,
    policies,
    summary,
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

export function getPoliciesByCompany(policies: Policy[] = DEMO_POLICIES) {
  const groups = policies.reduce((acc, policy) => {
    acc[policy.company] = acc[policy.company] ?? [];
    acc[policy.company].push(policy);
    return acc;
  }, {} as Record<string, Policy[]>);

  return Object.entries(groups).map(([company, companyPolicies]) => ({
    company,
    policies: companyPolicies,
    annualPremium: companyPolicies.reduce((sum, policy) => sum + policy.annualPremium, 0),
  }));
}

export function formatMoney(value: number) {
  return `NT$ ${value.toLocaleString("zh-TW")}`;
}

export function formatCoverage(key: CoverageKey, value: number) {
  const meta = COVERAGE_LABELS[key];
  return `${value.toLocaleString("zh-TW")} ${meta.unit}`;
}

export function formatPolicyContextForAi(policies: Policy[] = DEMO_POLICIES) {
  const summary = getPolicySummary(policies);
  const coverageLines = COVERAGE_ORDER.map((key) => {
    return `- ${COVERAGE_LABELS[key].label}：${formatCoverage(key, summary.coverage[key])}`;
  }).join("\n");

  const policyLines = policies.map((policy, index) => {
    const coverages = COVERAGE_ORDER
      .filter((key) => policy.coverages[key])
      .map((key) => `${COVERAGE_LABELS[key].label} ${formatCoverage(key, policy.coverages[key] ?? 0)}`)
      .join("、");
    return `${index + 1}. ${policy.company}｜${policy.name}｜${policy.role}｜${policy.status}｜年繳 ${policy.annualPremium.toLocaleString("zh-TW")} 元｜${coverages || "保障資料待補"}`;
  }).join("\n");

  return `【我的保單資料】
目前系統中有 ${summary.policyCount} 張保單、${summary.companyCount} 家保險公司，年繳保費 ${summary.premium.toLocaleString("zh-TW")} 元。

【保障總覽】
${coverageLines}

【保單清單】
${policyLines}

回答規則：
- 如果使用者問「我的保障」、「我可以申請什麼」、「我夠不夠」等問題，請優先根據上方個人保單資料回答。
- 開頭請點出「根據你目前系統中的 ${summary.policyCount} 張保單」。
- 不要把回答寫成一般保險知識介紹；除非個人保單資料不足，才補充一般原則。
- 涉及理賠金額時請用預估與需確認措辭。`;
}
