"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  fetchPolicyPortfolio,
  formatCoverage,
  formatMoney,
  getPolicyCompleteness,
  getPoliciesByCompany,
  getPolicySummary,
  type CoverageKey,
  type PolicyPortfolio,
} from "@/lib/demo-policies";
import { analyzePolicyCheck, formatGapValue, type CheckStatus } from "@/lib/policy-check";

interface Client {
  id: number;
  name: string;
  age: number;
  occupation: string | null;
  monthly_income: number | null;
  monthly_expense: number | null;
}

const STATUS_STYLE: Record<CheckStatus, string> = {
  ok: "bg-emerald-100 text-emerald-700",
  gap: "bg-amber-100 text-amber-700",
  missing: "bg-rose-100 text-rose-700",
};

const STATUS_LABEL: Record<CheckStatus, string> = {
  ok: "基本足夠",
  gap: "有缺口",
  missing: "未建立",
};

const REPORT_SECTIONS: Array<{ key: CoverageKey; title: string }> = [
  { key: "life", title: "壽險" },
  { key: "medical", title: "醫療險" },
  { key: "accident", title: "意外險" },
  { key: "cancer", title: "癌症險" },
  { key: "critical", title: "重大傷病險" },
  { key: "ltc", title: "失能 / 長照" },
];

const CLAIM_STATUS_STYLE = {
  ready: "bg-emerald-100 text-emerald-700",
  partial: "bg-amber-100 text-amber-700",
  missing: "bg-rose-100 text-rose-700",
};

const CLAIM_STATUS_LABEL = {
  ready: "可進入理賠比對",
  partial: "需補齊資料",
  missing: "尚無可用保障",
};

const PREMIUM_STYLE = {
  ok: "border-emerald-200 bg-emerald-50 text-emerald-900",
  review: "border-amber-200 bg-amber-50 text-amber-900",
  high: "border-rose-200 bg-rose-50 text-rose-900",
  unknown: "border-slate-200 bg-slate-50 text-slate-700",
};

export default function PolicyCheckPage() {
  const { id } = useParams<{ id: string }>();
  const [client, setClient] = useState<Client | null>(null);
  const [portfolio, setPortfolio] = useState<PolicyPortfolio>(() => ({
    profile: null,
    policies: [],
    summary: getPolicySummary([]),
  }));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const [clientRes, portfolioData] = await Promise.all([
          fetch(`/api/advisor/clients/${id}`, { cache: "no-store" }),
          fetchPolicyPortfolio(`advisor-client-${id}`).catch(() => fetchPolicyPortfolio()),
        ]);

        if (!clientRes.ok) throw new Error("not found");
        const clientData = await clientRes.json();

        if (!mounted) return;
        setClient(clientData);
        setPortfolio(portfolioData);
      } catch {
        if (mounted) setError("找不到此客戶或保單資料");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();

    return () => {
      mounted = false;
    };
  }, [id]);

  const checkResult = useMemo(() => {
    return analyzePolicyCheck(portfolio.policies, {
      age: client?.age,
      monthlyIncome: client?.monthly_income,
      monthlyExpense: client?.monthly_expense,
      occupation: client?.occupation,
    });
  }, [client?.age, client?.monthly_expense, client?.monthly_income, client?.occupation, portfolio.policies]);
  const companies = useMemo(() => getPoliciesByCompany(portfolio.policies), [portfolio.policies]);

  if (loading) return <div className="py-16 text-center text-sm text-gray-400">載入中...</div>;
  if (error || !client) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <p className="text-sm text-red-500">{error}</p>
        <Link href={`/advisor/clients/${id}`} className="text-sm text-blue-500">
          返回客戶頁
        </Link>
      </div>
    );
  }

  const profileId = `advisor-client-${client.id}`;
  const policyHref = `/policies?profile_id=${encodeURIComponent(profileId)}&owner_name=${encodeURIComponent(client.name)}&relation=${encodeURIComponent("本人")}`;
  const claimsHref = `/claims?profile_id=${encodeURIComponent(profileId)}&client_id=${client.id}&owner_name=${encodeURIComponent(client.name)}`;
  const reportPdfHref = `/api/policies/report/pdf?profile_id=${encodeURIComponent(profileId)}&owner_name=${encodeURIComponent(client.name)}&age=${client.age}&occupation=${encodeURIComponent(client.occupation || "")}&monthly_income=${client.monthly_income || 0}`;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8 print:max-w-none print:bg-white print:px-0 print:py-0">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between print:hidden">
        <div>
          <Link href={`/advisor/clients/${client.id}`} className="text-sm text-gray-400 hover:text-gray-600">
            返回客戶 360
          </Link>
          <p className="mt-3 text-sm font-bold text-amber-700">保單健診</p>
          <h1 className="mt-1 text-3xl font-bold text-gray-900">{client.name} 的保單健診報告</h1>
          <p className="mt-2 text-sm leading-6 text-gray-500">
            根據客戶既有保單統整六大保障，協助業務員找出保障缺口、待補資料與理賠服務前置條件。
          </p>
        </div>
        <div className="flex flex-wrap gap-2">
          <Link
            href={policyHref}
            className="rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-bold text-gray-700 transition hover:border-teal-300 hover:text-teal-700"
          >
            編輯保單
          </Link>
          <Link
            href={claimsHref}
            className="rounded-lg border border-gray-300 bg-white px-4 py-2.5 text-sm font-bold text-gray-700 transition hover:border-amber-300 hover:text-amber-700"
          >
            理賠服務
          </Link>
          <a
            href={reportPdfHref}
            className="rounded-lg bg-teal-700 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-teal-800"
          >
            下載正式 PDF
          </a>
          <button
            onClick={() => window.print()}
            className="rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800"
            type="button"
          >
            列印 / 另存 PDF
          </button>
        </div>
      </div>

      <section className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5 print:hidden">
        <Metric label="健診分數" value={`${checkResult.score} 分`} tone="text-rose-600" />
        <Metric label="保單總數" value={`${checkResult.policyCount} 張`} tone="text-teal-700" />
        <Metric label="保險公司" value={`${checkResult.companyCount} 家`} tone="text-slate-950" />
        <Metric label="年繳保費" value={formatMoney(checkResult.annualPremium)} tone="text-amber-600" />
        <Metric label="保費收入比" value={checkResult.premiumRatio === null ? "待補" : `${Math.round(checkResult.premiumRatio * 100)}%`} tone="text-sky-700" />
      </section>

      <PolicyCompletenessPanel policies={portfolio.policies} policyHref={policyHref} />

      <section className="mb-5 rounded-xl border border-gray-200 bg-white p-5 shadow-sm print:hidden">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <h2 className="text-lg font-bold text-gray-900">保障缺口分析</h2>
            <p className="mt-1 text-xs font-bold text-gray-400">{checkResult.targetBasis.join("・")}</p>
          </div>
          <span className="text-xs font-bold text-gray-400">建議基準已依客戶資料動態估算</span>
        </div>
        <CoverageTable checkResult={checkResult} />
      </section>

      <PolicyCheckInsightPanels checkResult={checkResult} />

      <div className="mb-6 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px] print:hidden">
        <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">投保內容整理</h2>
          <CompanyList companies={companies} />
        </section>

        <section className="rounded-xl border border-rose-200 bg-rose-50 p-5">
          <h2 className="text-lg font-bold text-rose-950">優先建議</h2>
          <div className="mt-4 space-y-3">
            {checkResult.priorities.length === 0 && checkResult.policyCount > 0 && (
              <Advice text="六大保障沒有明顯缺口，下一步建議檢查條款限制、保費效率與保障重複。" />
            )}
            {checkResult.priorities.map((item) => (
              <Advice key={item.key} text={`${item.label}目前缺口 ${formatCoverage(item.key, item.gap)}，建議優先與客戶確認家庭責任與預算。`} />
            ))}
            {checkResult.policyCount === 0 && <Advice text="尚未輸入既有保單，這份健診目前只能作為流程預覽，不能作為有效分析。" />}
          </div>
        </section>
      </div>

      <section id="report" className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm print:rounded-none print:border-0 print:p-8 print:shadow-none">
        <div className="mb-6 border-b border-gray-200 pb-5">
          <p className="text-sm font-bold text-teal-700">Insurance Policy Review</p>
          <div className="mt-2 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
            <div>
              <h2 className="text-3xl font-bold text-gray-950">保單健診報告</h2>
              <p className="mt-2 text-sm text-gray-500">報告日期：{new Date().toLocaleDateString("zh-TW")}</p>
            </div>
            <div className="rounded-xl bg-slate-950 px-5 py-4 text-white">
              <p className="text-xs font-bold text-slate-300">健診分數</p>
              <p className="mt-1 text-3xl font-bold tabular-nums">{checkResult.score}</p>
            </div>
          </div>
        </div>

        <section className="mb-6 grid gap-3 md:grid-cols-3">
          <div className="rounded-xl border border-teal-100 bg-teal-50 p-4">
            <p className="text-xs font-bold text-teal-700">總評</p>
            <p className="mt-2 text-sm font-bold leading-6 text-teal-950">
              {checkResult.score >= 80 ? "保障架構大致完整" : checkResult.score >= 50 ? "保障與資料仍需補強" : "目前資料不足，需先整理既有保單"}
            </p>
          </div>
          <div className="rounded-xl border border-amber-100 bg-amber-50 p-4">
            <p className="text-xs font-bold text-amber-700">優先處理</p>
            <p className="mt-2 text-sm font-bold leading-6 text-amber-950">
              {checkResult.priorities[0] ? `${checkResult.priorities[0].label}缺口 ${formatGapValue(checkResult.priorities[0])}` : "檢查條款限制與重複投保"}
            </p>
          </div>
          <div className="rounded-xl border border-sky-100 bg-sky-50 p-4">
            <p className="text-xs font-bold text-sky-700">理賠前置</p>
            <p className="mt-2 text-sm font-bold leading-6 text-sky-950">
              {portfolio.summary.incomplete > 0 ? `${portfolio.summary.incomplete} 張保單需補齊資料` : "可進入理賠文件比對流程"}
            </p>
          </div>
        </section>

        <div className="grid gap-5 lg:grid-cols-[280px_minmax(0,1fr)]">
          <aside className="rounded-xl bg-gray-50 p-4 text-sm print:border print:border-gray-200">
            <Info label="客戶姓名" value={client.name} />
            <Info label="年齡" value={`${client.age} 歲`} />
            <Info label="職業" value={client.occupation || "待補"} />
            <Info label="年收入估算" value={client.monthly_income ? formatMoney(client.monthly_income * 12) : "待補"} />
            <Info label="保單張數" value={`${checkResult.policyCount} 張`} />
            <Info label="保險公司" value={`${checkResult.companyCount} 家`} />
            <Info label="年繳保費" value={formatMoney(checkResult.annualPremium)} />
            <Info label="保費收入比" value={checkResult.premiumRatio === null ? "待補" : `${Math.round(checkResult.premiumRatio * 100)}%`} />
          </aside>

          <main>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {REPORT_SECTIONS.map(({ key, title }) => {
                const check = checkResult.checks.find((item) => item.key === key);
                return (
                  <div key={key} className="rounded-xl border border-gray-100 p-4">
                    <p className="text-xs font-bold text-gray-400">{title}</p>
                    <p className="mt-2 text-xl font-bold text-gray-900">{formatCoverage(key, portfolio.summary.coverage[key])}</p>
                    {check && (
                      <>
                        <p className={`mt-2 text-xs font-bold ${check.status === "ok" ? "text-emerald-700" : "text-rose-600"}`}>
                          {STATUS_LABEL[check.status]}
                        </p>
                        <p className="mt-2 text-xs leading-5 text-gray-400">建議基準：{formatCoverage(key, check.target)}</p>
                      </>
                    )}
                  </div>
                );
              })}
            </div>

            <section className="mt-6">
              <h3 className="text-lg font-bold text-gray-900">健診摘要</h3>
              <div className="mt-3 grid gap-2">
                {checkResult.warnings.length === 0 ? (
                  <p className="rounded-xl bg-emerald-50 px-4 py-3 text-sm font-medium leading-6 text-emerald-900">
                    目前資料可進行初步健診，後續仍需確認條款限制與客戶最新家庭責任。
                  </p>
                ) : (
                  checkResult.warnings.map((warning) => (
                    <p key={warning} className="rounded-xl bg-amber-50 px-4 py-3 text-sm font-medium leading-6 text-amber-900">
                      {warning}
                    </p>
                  ))
                )}
              </div>
            </section>

            <section className="mt-6">
              <h3 className="text-lg font-bold text-gray-900">優先處理項目</h3>
              <div className="mt-3 grid gap-2">
                {checkResult.priorities.length === 0 ? (
                  <p className="rounded-xl bg-gray-50 px-4 py-3 text-sm leading-6 text-gray-600">
                    六大保障未見明顯缺口，建議進一步檢查重複投保、實支實付條款與理賠文件可取得性。
                  </p>
                ) : (
                  checkResult.priorities.map((item) => (
                    <p key={item.key} className="rounded-xl bg-gray-50 px-4 py-3 text-sm leading-6 text-gray-700">
                      {item.label}：現有 {formatCoverage(item.key, item.current)}，建議 {formatCoverage(item.key, item.target)}，
                      缺口 {formatGapValue(item)}。
                    </p>
                  ))
                )}
              </div>
            </section>
          </main>
        </div>

        <section className="mt-6">
          <h3 className="text-lg font-bold text-gray-900">保障明細表</h3>
          <div className="mt-3">
            <CoverageTable checkResult={checkResult} compact />
          </div>
        </section>

        <section className="mt-6">
          <h3 className="text-lg font-bold text-gray-900">健診重點判讀</h3>
          <PolicyCheckInsightPanels checkResult={checkResult} inReport />
        </section>

        <section className="mt-6">
          <h3 className="text-lg font-bold text-gray-900">投保內容</h3>
          <CompanyList companies={companies} compact />
        </section>

        <p className="mt-6 rounded-xl bg-slate-950 p-4 text-xs leading-6 text-white">
          本報告為依已輸入保單資料產生之初步保單健診，正式建議仍需由持證業務員確認保單條款、除外責任、
          續保條件、實支實付限額、家庭責任與客戶最新財務狀況。
        </p>
      </section>
    </div>
  );
}

function PolicyCheckInsightPanels({
  checkResult,
  inReport = false,
}: {
  checkResult: ReturnType<typeof analyzePolicyCheck>;
  inReport?: boolean;
}) {
  const duplicateWarnings = checkResult.duplicateWarnings;
  const claimReadyCount = checkResult.claimReadiness.filter((item) => item.status === "ready").length;

  return (
    <section className={`${inReport ? "mt-3" : "mb-6 print:hidden"} grid gap-4 lg:grid-cols-3`}>
      <div className={`rounded-xl border p-5 ${PREMIUM_STYLE[checkResult.premiumReview.status]}`}>
        <p className="text-xs font-bold opacity-75">保費檢查</p>
        <h3 className="mt-2 text-lg font-bold">{checkResult.premiumReview.label}</h3>
        <p className="mt-2 text-sm leading-6">{checkResult.premiumReview.message}</p>
      </div>

      <div className="rounded-xl border border-violet-100 bg-violet-50 p-5 text-violet-950">
        <p className="text-xs font-bold text-violet-700">重複保障提醒</p>
        <h3 className="mt-2 text-lg font-bold">{duplicateWarnings.length} 項需檢查</h3>
        <div className="mt-3 space-y-2">
          {duplicateWarnings.length === 0 ? (
            <p className="text-sm leading-6 text-violet-800">目前沒有明顯超過建議基準的保障，後續可檢查條款限制與保費結構。</p>
          ) : (
            duplicateWarnings.slice(0, 3).map((warning) => (
              <p key={warning} className="rounded-lg bg-white/70 px-3 py-2 text-sm leading-6 text-violet-900">
                {warning}
              </p>
            ))
          )}
        </div>
      </div>

      <div className="rounded-xl border border-sky-100 bg-sky-50 p-5 text-sky-950">
        <p className="text-xs font-bold text-sky-700">理賠可用性</p>
        <h3 className="mt-2 text-lg font-bold">{claimReadyCount} / {checkResult.claimReadiness.length} 項可比對</h3>
        <div className="mt-3 space-y-2">
          {checkResult.claimReadiness.slice(0, inReport ? 6 : 4).map((item) => (
            <div key={item.key} className="rounded-lg bg-white/80 px-3 py-2">
              <div className="flex items-center justify-between gap-2">
                <p className="text-sm font-bold text-sky-950">{item.label}</p>
                <span className={`shrink-0 rounded px-2 py-1 text-xs font-bold ${CLAIM_STATUS_STYLE[item.status]}`}>
                  {CLAIM_STATUS_LABEL[item.status]}
                </span>
              </div>
              <p className="mt-1 text-xs leading-5 text-sky-800">{item.nextStep}</p>
            </div>
          ))}
        </div>
      </div>
    </section>
  );
}

function CoverageTable({
  checkResult,
  compact = false,
}: {
  checkResult: ReturnType<typeof analyzePolicyCheck>;
  compact?: boolean;
}) {
  return (
    <div className="overflow-hidden rounded-xl border border-gray-100">
      <div className="grid grid-cols-[1.1fr_1fr_1fr_1fr_110px] bg-gray-50 px-4 py-3 text-xs font-bold text-gray-500">
        <span>保障項目</span>
        <span className="text-right">現有保障</span>
        <span className="text-right">建議基準</span>
        <span className="text-right">缺口</span>
        <span className="text-right">狀態</span>
      </div>
      {checkResult.checks.map((check) => (
        <div
          key={check.key}
          className="grid grid-cols-[1.1fr_1fr_1fr_1fr_110px] items-center border-t border-gray-100 px-4 py-3 text-sm"
        >
          <div>
            <p className="font-bold text-gray-900">{check.label}</p>
            {!compact && <p className="mt-1 text-xs leading-5 text-gray-400">{check.targetReason}</p>}
          </div>
          <span className="text-right tabular-nums text-gray-600">{formatCoverage(check.key, check.current)}</span>
          <span className="text-right tabular-nums text-gray-600">{formatCoverage(check.key, check.target)}</span>
          <span className={`text-right font-bold tabular-nums ${check.gap > 0 ? "text-rose-600" : "text-emerald-700"}`}>
            {check.gap > 0 ? formatGapValue(check) : "無缺口"}
          </span>
          <span className="text-right">
            <span className={`inline-flex rounded px-2 py-1 text-xs font-bold ${STATUS_STYLE[check.status]}`}>
              {STATUS_LABEL[check.status]}
            </span>
          </span>
        </div>
      ))}
    </div>
  );
}

function PolicyCompletenessPanel({
  policies,
  policyHref,
}: {
  policies: PolicyPortfolio["policies"];
  policyHref: string;
}) {
  const items = policies
    .map((policy) => ({ policy, completeness: getPolicyCompleteness(policy) }))
    .filter((item) => item.completeness.missing_count > 0)
    .sort((a, b) => a.completeness.score - b.completeness.score);

  if (policies.length === 0) {
    return (
      <section className="mb-5 rounded-xl border border-rose-200 bg-rose-50 p-5 print:hidden">
        <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <h2 className="text-lg font-bold text-rose-950">保單資料尚未建立</h2>
            <p className="mt-1 text-sm leading-6 text-rose-800">請先輸入客戶既有保單，否則健診分析與理賠比對都沒有可用基礎。</p>
          </div>
          <Link href={policyHref} className="w-fit rounded-lg bg-rose-700 px-4 py-2 text-sm font-bold text-white hover:bg-rose-800">
            建立保單資料
          </Link>
        </div>
      </section>
    );
  }

  if (items.length === 0) {
    return (
      <section className="mb-5 rounded-xl border border-emerald-200 bg-emerald-50 p-5 print:hidden">
        <h2 className="text-lg font-bold text-emerald-950">保單資料完整度良好</h2>
        <p className="mt-1 text-sm leading-6 text-emerald-800">目前已輸入保單可支援初步健診，後續仍建議確認條款限制與最新保單批註。</p>
      </section>
    );
  }

  return (
    <section className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-5 print:hidden">
      <div className="mb-4 flex flex-col gap-3 sm:flex-row sm:items-end sm:justify-between">
        <div>
          <h2 className="text-lg font-bold text-amber-950">保單資料完整度檢查</h2>
          <p className="mt-1 text-sm leading-6 text-amber-800">以下保單資料不足，補齊後健診與理賠試算會更準。</p>
        </div>
        <Link href={policyHref} className="w-fit rounded-lg bg-white px-4 py-2 text-sm font-bold text-amber-800 ring-1 ring-amber-200 hover:ring-amber-400">
          前往補資料
        </Link>
      </div>
      <div className="grid gap-3 md:grid-cols-2">
        {items.slice(0, 4).map(({ policy, completeness }) => (
          <div key={policy.id} className="rounded-xl bg-white p-4 ring-1 ring-amber-100">
            <div className="flex items-start justify-between gap-3">
              <div className="min-w-0">
                <p className="truncate text-sm font-bold text-gray-950">{policy.name}</p>
                <p className="mt-1 text-xs text-gray-400">{policy.company}</p>
              </div>
              <span className="rounded-lg bg-amber-100 px-2 py-1 text-xs font-bold text-amber-700">{completeness.score}%</span>
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {completeness.missing.slice(0, 5).map((item) => (
                <span key={item.key} className="rounded-lg bg-amber-50 px-2 py-1 text-xs font-bold text-amber-800">
                  {item.label}
                </span>
              ))}
            </div>
          </div>
        ))}
      </div>
    </section>
  );
}

function CompanyList({
  companies,
  compact = false,
}: {
  companies: ReturnType<typeof getPoliciesByCompany>;
  compact?: boolean;
}) {
  return (
    <div className="space-y-2">
      {companies.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-200 px-4 py-6 text-center text-sm text-gray-400">
          尚未建立保單資料
        </div>
      )}
      {companies.map((group) => (
        <div key={group.company} className="rounded-xl bg-gray-50 px-4 py-3">
          <div className="flex items-center justify-between text-sm">
            <p className="font-bold text-gray-900">{group.company}</p>
            <p className="font-bold tabular-nums text-gray-700">{formatMoney(group.annualPremium)}</p>
          </div>
          <div className="mt-2 space-y-1">
            {group.policies.map((policy) => (
              <div key={policy.id} className="grid grid-cols-[minmax(0,1fr)_80px_90px] gap-2 text-xs text-gray-500">
                <span className="truncate">{policy.name}</span>
                <span>{policy.status}</span>
                {!compact && <span className="text-right">{formatMoney(policy.annualPremium)}</span>}
              </div>
            ))}
          </div>
        </div>
      ))}
    </div>
  );
}

function Metric({ label, value, tone }: { label: string; value: string; tone: string }) {
  return (
    <div className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-medium text-gray-500">{label}</p>
      <p className={`mt-2 text-2xl font-bold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div className="mb-3">
      <p className="text-xs font-bold text-gray-400">{label}</p>
      <p className="mt-1 font-bold text-gray-800">{value}</p>
    </div>
  );
}

function Advice({ text }: { text: string }) {
  return (
    <div className="rounded-xl bg-white px-3 py-2 text-sm font-medium leading-6 text-rose-950">
      {text}
    </div>
  );
}
