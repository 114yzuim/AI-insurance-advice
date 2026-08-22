"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  COVERAGE_LABELS,
  COVERAGE_ORDER,
  fetchPolicyPortfolio,
  formatCoverage,
  formatMoney,
  getPoliciesByCompany,
  getPolicySummary,
  type PolicyPortfolio,
} from "@/lib/demo-policies";
import { analyzePolicyCheck, formatGapValue, type CheckStatus } from "@/lib/policy-check";

interface Client {
  id: number;
  name: string;
  age: number;
  occupation: string | null;
  monthly_income: number | null;
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

  const checkResult = useMemo(() => analyzePolicyCheck(portfolio.policies), [portfolio.policies]);
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

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
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
          <a
            href="#report"
            className="rounded-lg bg-slate-950 px-4 py-2.5 text-sm font-bold text-white transition hover:bg-slate-800"
          >
            查看報告
          </a>
        </div>
      </div>

      <section className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-5">
        <Metric label="健診分數" value={`${checkResult.score} 分`} tone="text-rose-600" />
        <Metric label="保單總數" value={`${checkResult.policyCount} 張`} tone="text-teal-700" />
        <Metric label="保險公司" value={`${checkResult.companyCount} 家`} tone="text-slate-950" />
        <Metric label="年繳保費" value={formatMoney(checkResult.annualPremium)} tone="text-amber-600" />
        <Metric label="待補資料" value={`${checkResult.incompleteCount} 張`} tone="text-sky-700" />
      </section>

      {checkResult.warnings.length > 0 && (
        <section className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-4">
          <h2 className="text-sm font-bold text-amber-950">健診提醒</h2>
          <div className="mt-3 grid gap-2">
            {checkResult.warnings.map((warning) => (
              <p key={warning} className="rounded-lg bg-white px-3 py-2 text-sm font-medium text-amber-900">
                {warning}
              </p>
            ))}
          </div>
        </section>
      )}

      <section className="mb-5 rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
        <div className="mb-4 flex items-center justify-between">
          <h2 className="text-lg font-bold text-gray-900">保障缺口分析</h2>
          <span className="text-xs font-bold text-gray-400">目標值可在下一階段改為依家庭責任計算</span>
        </div>
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
                <p className="mt-1 text-xs leading-5 text-gray-400">{check.suggestion}</p>
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
      </section>

      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">投保內容整理</h2>
          <div className="mt-4 space-y-2">
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
                    <div key={policy.id} className="flex items-center justify-between text-xs text-gray-500">
                      <span className="truncate">{policy.name}</span>
                      <span className="shrink-0">{policy.status}</span>
                    </div>
                  ))}
                </div>
              </div>
            ))}
          </div>
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

      <section id="report" className="rounded-xl border border-gray-200 bg-white p-6 shadow-sm">
        <div className="mb-5 flex flex-col gap-2 border-b border-gray-100 pb-4 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-bold text-teal-700">報告預覽</p>
            <h2 className="text-2xl font-bold text-gray-900">保單健診報告</h2>
          </div>
          <span className="text-xs font-bold text-gray-400">PDF 匯出會在下一階段接上</span>
        </div>

        <div className="grid gap-5 lg:grid-cols-[260px_minmax(0,1fr)]">
          <aside className="rounded-xl bg-gray-50 p-4 text-sm">
            <Info label="客戶姓名" value={client.name} />
            <Info label="年齡" value={`${client.age} 歲`} />
            <Info label="職業" value={client.occupation || "待補"} />
            <Info label="年收入估算" value={client.monthly_income ? formatMoney(client.monthly_income * 12) : "待補"} />
            <Info label="保單張數" value={`${checkResult.policyCount} 張`} />
            <Info label="年繳保費" value={formatMoney(checkResult.annualPremium)} />
          </aside>

          <main>
            <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
              {COVERAGE_ORDER.map((key) => {
                const check = checkResult.checks.find((item) => item.key === key);
                return (
                  <div key={key} className="rounded-xl border border-gray-100 p-4">
                    <p className="text-xs font-bold text-gray-400">{COVERAGE_LABELS[key].label}</p>
                    <p className="mt-2 text-xl font-bold text-gray-900">{formatCoverage(key, portfolio.summary.coverage[key])}</p>
                    {check && (
                      <p className={`mt-2 text-xs font-bold ${check.status === "ok" ? "text-emerald-700" : "text-rose-600"}`}>
                        {STATUS_LABEL[check.status]}
                      </p>
                    )}
                  </div>
                );
              })}
            </div>

            <div className="mt-5 rounded-xl bg-slate-950 p-4 text-sm leading-6 text-white">
              本次健診根據已輸入的 {checkResult.policyCount} 張保單進行初步分析。若要作為正式建議，需再確認保單條款、
              除外責任、續保條件、實支實付限額與客戶家庭責任。
            </div>
          </main>
        </div>
      </section>
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
