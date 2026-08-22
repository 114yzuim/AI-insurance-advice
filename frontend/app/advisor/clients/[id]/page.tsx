"use client";

import Link from "next/link";
import { useParams } from "next/navigation";
import { useEffect, useMemo, useState } from "react";
import {
  COVERAGE_LABELS,
  COVERAGE_ORDER,
  DEMO_POLICIES,
  fetchPolicyPortfolio,
  formatCoverage,
  formatMoney,
  getPoliciesByCompany,
  getPolicySummary,
  type PolicyPortfolio,
} from "@/lib/demo-policies";
import { analyzePolicyCheck } from "@/lib/policy-check";

interface Client {
  id: number;
  name: string;
  age: number;
  email: string | null;
  phone: string | null;
  gender: string | null;
  occupation: string | null;
  status: string;
  monthly_income: number | null;
  monthly_expense: number | null;
}

const GENDER: Record<string, string> = { M: "男", F: "女" };
const STATUS_LABEL: Record<string, string> = { new: "新客戶", questionnaire_done: "健診完成" };

function fmt(n: number | null | undefined): string {
  if (n == null) return "待補";
  return n.toLocaleString("zh-TW");
}

export default function ClientHubPage() {
  const { id } = useParams<{ id: string }>();
  const [client, setClient] = useState<Client | null>(null);
  const [portfolio, setPortfolio] = useState<PolicyPortfolio>(() => ({
    profile: null,
    policies: DEMO_POLICIES,
    summary: getPolicySummary(DEMO_POLICIES),
  }));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const summary = portfolio.summary;
  const checkResult = useMemo(() => analyzePolicyCheck(portfolio.policies), [portfolio.policies]);
  const companies = useMemo(() => getPoliciesByCompany(portfolio.policies), [portfolio.policies]);

  useEffect(() => {
    let mounted = true;

    async function load() {
      try {
        const [clientRes, portfolioData] = await Promise.all([
          fetch(`/api/advisor/clients/${id}`, { cache: "no-store" }),
          fetchPolicyPortfolio().catch(() => ({
            profile: null,
            policies: DEMO_POLICIES,
            summary: getPolicySummary(DEMO_POLICIES),
          })),
        ]);

        if (!clientRes.ok) throw new Error("not found");
        const clientData = await clientRes.json();

        if (!mounted) return;
        setClient(clientData);
        setPortfolio(portfolioData);
      } catch {
        if (mounted) setError("找不到此客戶");
      } finally {
        if (mounted) setLoading(false);
      }
    }

    load();

    return () => {
      mounted = false;
    };
  }, [id]);

  if (loading) return <div className="py-16 text-center text-sm text-gray-400">載入中...</div>;
  if (error || !client) {
    return (
      <div className="mx-auto max-w-3xl px-4 py-8">
        <p className="text-sm text-red-500">{error}</p>
        <Link href="/advisor" className="text-sm text-blue-500">
          返回客戶列表
        </Link>
      </div>
    );
  }

  const profileId = `advisor-client-${client.id}`;
  const policyHref = `/policies?profile_id=${encodeURIComponent(profileId)}&owner_name=${encodeURIComponent(client.name)}&relation=${encodeURIComponent("本人")}`;

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6">
        <Link href="/advisor" className="text-sm text-gray-400 hover:text-gray-600">
          返回客戶列表
        </Link>
        <div className="mt-3 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-bold text-amber-700">客戶 360</p>
            <h1 className="mt-1 text-3xl font-bold text-gray-900">{client.name}</h1>
            <p className="mt-2 text-sm leading-6 text-gray-500">
              管理此客戶的既有保單、保單健診、報告紀錄與理賠服務。
            </p>
          </div>
          <span className="w-fit rounded-lg bg-gray-100 px-3 py-2 text-xs font-bold text-gray-600">
            {STATUS_LABEL[client.status] ?? client.status}
          </span>
        </div>
      </div>

      <section className="mb-5 grid gap-3 sm:grid-cols-2 lg:grid-cols-4">
        <Metric label="保單總數" value={`${summary.policyCount} 張`} tone="text-teal-700" />
        <Metric label="保險公司" value={`${summary.companyCount} 家`} tone="text-slate-950" />
        <Metric label="年繳保費" value={formatMoney(summary.premium)} tone="text-amber-600" />
        <Metric label="健診分數" value={`${checkResult.score} 分`} tone="text-rose-600" />
      </section>

      <div className="mb-5 grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <div className="mb-4 flex items-center justify-between">
            <h2 className="text-lg font-bold text-gray-900">六大保障總覽</h2>
            <Link href={`/advisor/clients/${client.id}/policy-check`} className="text-sm font-bold text-teal-700 hover:text-teal-900">
              查看健診
            </Link>
          </div>
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {COVERAGE_ORDER.map((key) => (
              <div key={key} className="rounded-xl bg-gray-50 p-3">
                <p className="text-xs font-bold text-gray-400">{COVERAGE_LABELS[key].label}</p>
                <p className="mt-1 text-base font-bold text-gray-900">{formatCoverage(key, summary.coverage[key])}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">客戶資料</h2>
          <div className="mt-4 grid grid-cols-2 gap-3 text-sm">
            <Info label="年齡" value={`${client.age} 歲`} />
            <Info label="性別" value={GENDER[client.gender ?? ""] ?? "待補"} />
            <Info label="職業" value={client.occupation || "待補"} />
            <Info label="電話" value={client.phone || "待補"} />
            <Info label="Email" value={client.email || "待補"} wide />
            <Info label="月收入" value={`${fmt(client.monthly_income)} 元`} />
            <Info label="月支出" value={`${fmt(client.monthly_expense)} 元`} />
          </div>
        </section>
      </div>

      <section className="mb-5 rounded-xl border border-amber-200 bg-amber-50 p-5">
        <div className="mb-4 flex flex-col gap-2 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-bold text-amber-800">保單健診流程</p>
            <h2 className="text-lg font-bold text-amber-950">先整理既有保單，再判斷缺口與理賠可用性</h2>
          </div>
          <span className="text-xs font-bold text-amber-700">
            {summary.policyCount > 0 ? "可進行初步健診" : "請先建立保單資料"}
          </span>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          <WorkflowCard title="保單資料" text="上傳或手動輸入客戶現有保單。" href={policyHref} />
          <WorkflowCard title="保單健診" text="統整保障、缺口、保費與待補欄位。" href={`/advisor/clients/${client.id}/policy-check`} />
          <WorkflowCard title="健診報告" text="產出可給客戶說明的報告預覽。" href={`/advisor/clients/${client.id}/policy-check#report`} />
          <WorkflowCard title="理賠服務" text="以既有保單比對可申請項目。" href="/claims" />
        </div>
      </section>

      <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_340px]">
        <section className="rounded-xl border border-gray-200 bg-white p-5 shadow-sm">
          <h2 className="text-lg font-bold text-gray-900">保險公司與保費</h2>
          <div className="mt-4 space-y-2">
            {companies.length === 0 && (
              <div className="rounded-xl border border-dashed border-gray-200 px-4 py-6 text-center text-sm text-gray-400">
                尚未建立保單資料
              </div>
            )}
            {companies.map((group) => (
              <div key={group.company} className="flex items-center justify-between rounded-xl bg-gray-50 px-4 py-3 text-sm">
                <div>
                  <p className="font-bold text-gray-900">{group.company}</p>
                  <p className="mt-0.5 text-xs text-gray-400">{group.policies.length} 張保單</p>
                </div>
                <p className="text-right font-bold tabular-nums text-gray-700">{formatMoney(group.annualPremium)}</p>
              </div>
            ))}
          </div>
        </section>

        <section className="rounded-xl border border-amber-200 bg-amber-50 p-5">
          <h2 className="text-lg font-bold text-amber-950">優先待辦</h2>
          <div className="mt-4 space-y-3">
            {checkResult.priorities.length === 0 && summary.policyCount > 0 ? (
              <Task text="目前六大保障沒有明顯缺口，可進一步檢查條款限制與重複保障。" />
            ) : (
              checkResult.priorities.map((item) => (
                <Task key={item.key} text={`${item.label}缺口 ${formatCoverage(item.key, item.gap)}，建議優先確認。`} />
              ))
            )}
            {summary.policyCount === 0 && <Task text="請先輸入客戶現有保單，否則無法產生有效健診。" />}
            {summary.incomplete > 0 && <Task text={`${summary.incomplete} 張保單資料待補，需補齊保額、保費或保單號碼。`} />}
          </div>
        </section>
      </div>
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

function Info({ label, value, wide = false }: { label: string; value: string; wide?: boolean }) {
  return (
    <div className={wide ? "col-span-2" : ""}>
      <span className="text-gray-400">{label}</span>
      <div className="mt-0.5 truncate font-medium tabular-nums text-gray-800">{value}</div>
    </div>
  );
}

function WorkflowCard({ title, text, href }: { title: string; text: string; href: string }) {
  return (
    <Link href={href} className="rounded-xl border border-amber-200 bg-white p-4 shadow-sm transition hover:border-amber-400 hover:shadow-md">
      <p className="font-bold text-gray-900">{title}</p>
      <p className="mt-2 text-xs leading-5 text-gray-500">{text}</p>
      <p className="mt-4 text-xs font-bold text-amber-700">進入</p>
    </Link>
  );
}

function Task({ text }: { text: string }) {
  return (
    <div className="rounded-xl bg-white px-3 py-2 text-sm font-medium leading-6 text-amber-950">
      {text}
    </div>
  );
}
