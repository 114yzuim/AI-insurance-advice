"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

interface Client {
  id: number;
  name: string;
  age: number;
  occupation: string | null;
  status: string;
  email: string | null;
  monthly_investable: number | null;
}

interface PolicyMetrics {
  policyCount: number;
  incompletePolicies: number;
  averageCompleteness: number;
}

const EMPTY_POLICY_METRICS: PolicyMetrics = {
  policyCount: 0,
  incompletePolicies: 0,
  averageCompleteness: 0,
};

interface InsuranceProfile {
  id: string;
  owner_name?: string;
  policy_count?: number;
  incomplete_policy_count?: number;
  average_completeness?: number;
}

interface ClaimCase {
  id: number;
  owner_name: string;
  status: string;
  estimated_total: number;
  next_follow_up_date: string;
  updated_at: string;
}

interface ClaimMetrics {
  openClaims: number;
  followUpClaims: number;
  cases: ClaimCase[];
}

const EMPTY_CLAIM_METRICS: ClaimMetrics = {
  openClaims: 0,
  followUpClaims: 0,
  cases: [],
};

function formatDashboardMoney(value: number) {
  return `NT$ ${Number(value || 0).toLocaleString("zh-TW")}`;
}

const STATUS_LABEL: Record<string, string> = {
  new: "新客戶",
  questionnaire_done: "健診完成",
};

const STATUS_COLOR: Record<string, string> = {
  new: "bg-gray-100 text-gray-600",
  questionnaire_done: "bg-green-100 text-green-700",
};

async function fetchPolicyMetrics(): Promise<PolicyMetrics> {
  const res = await fetch("/api/policies/profiles", { cache: "no-store" });

  if (!res.ok) {
    throw new Error("Failed to load policies");
  }

  const profiles: InsuranceProfile[] = await res.json();
  const policyCount = profiles.reduce((sum, profile) => sum + Number(profile.policy_count || 0), 0);
  const incompletePolicies = profiles.reduce((sum, profile) => sum + Number(profile.incomplete_policy_count || 0), 0);
  const weightedCompleteness = profiles.reduce(
    (sum, profile) => sum + Number(profile.average_completeness || 0) * Number(profile.policy_count || 0),
    0,
  );

  return {
    policyCount,
    incompletePolicies,
    averageCompleteness: policyCount ? Math.round(weightedCompleteness / policyCount) : 0,
  };
}

async function fetchClaimMetrics(): Promise<ClaimMetrics> {
  const res = await fetch("/api/claims/cases?profile_id=all", { cache: "no-store" });
  if (!res.ok) throw new Error("Failed to load claim cases");
  const cases: ClaimCase[] = await res.json();
  const openCases = cases.filter((claimCase) => claimCase.status !== "已結案");
  const today = new Date().toISOString().slice(0, 10);
  return {
    openClaims: openCases.length,
    followUpClaims: openCases.filter((claimCase) => claimCase.next_follow_up_date && claimCase.next_follow_up_date <= today).length,
    cases: openCases.slice(0, 5),
  };
}

export default function AdvisorPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [policyMetrics, setPolicyMetrics] = useState<PolicyMetrics>(EMPTY_POLICY_METRICS);
  const [claimMetrics, setClaimMetrics] = useState<ClaimMetrics>(EMPTY_CLAIM_METRICS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadDashboard() {
      try {
        const [clientsRes, metrics, claims] = await Promise.all([
          fetch("/api/advisor/clients", { cache: "no-store" }),
          fetchPolicyMetrics().catch(() => EMPTY_POLICY_METRICS),
          fetchClaimMetrics().catch(() => EMPTY_CLAIM_METRICS),
        ]);

        if (!clientsRes.ok) {
          throw new Error("Failed to load clients");
        }

        const clientsData = await clientsRes.json();

        if (!isMounted) return;

        setClients(Array.isArray(clientsData) ? clientsData : clientsData.items ?? []);
        setPolicyMetrics(metrics);
        setClaimMetrics(claims);
      } catch {
        if (isMounted) {
          setError("資料載入失敗，請稍後再試。");
          setPolicyMetrics(EMPTY_POLICY_METRICS);
          setClaimMetrics(EMPTY_CLAIM_METRICS);
        }
      } finally {
        if (isMounted) {
          setLoading(false);
        }
      }
    }

    loadDashboard();

    return () => {
      isMounted = false;
    };
  }, []);

  const pendingHealthChecks = useMemo(
    () => clients.filter((client) => client.status !== "questionnaire_done").length,
    [clients],
  );

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`確定要刪除「${name}」嗎？此操作無法復原。`)) return;

    await fetch(`/api/advisor/clients/${id}`, { method: "DELETE" });
    setClients((prev) => prev.filter((client) => client.id !== id));
  };

  const dashboardItems = [
    { label: "客戶", value: `${clients.length} 人`, tone: "text-slate-950" },
    { label: "保單總數", value: `${policyMetrics.policyCount} 張`, tone: "text-teal-700" },
    { label: "待完成保單健診", value: `${pendingHealthChecks} 人`, tone: "text-amber-600" },
    { label: "保單資料不完整", value: `${policyMetrics.incompletePolicies} 張`, tone: "text-sky-700" },
    { label: "待處理理賠", value: `${claimMetrics.openClaims} 件`, tone: "text-rose-600" },
    { label: "平均資料完整度", value: `${policyMetrics.averageCompleteness}%`, tone: "text-violet-700" },
  ];

  const workflowItems = [
    {
      title: "建立客戶與家庭成員",
      text: "先完成客戶基本資料，之後每位家庭成員都可以建立自己的保單 Profile。",
      href: "/advisor/clients/new",
    },
    {
      title: "輸入既有保單",
      text: "以既有保單為核心，補齊保險公司、主附約、保費與六大保障欄位。",
      href: "/policies",
    },
    {
      title: "產生保單健診",
      text: "從現有保障統整出缺口、重複、待補資料與顧問建議。",
      href: clients[0] ? `/advisor/clients/${clients[0].id}/policy-check` : "/advisor",
    },
    {
      title: "追蹤理賠服務",
      text: "健診完成後，理賠中心才能依客戶保單比對可申請項目。",
      href: "/claims",
    },
  ];

  const advisorTodos = [
    ...(policyMetrics.incompletePolicies > 0
      ? [
          {
            title: "補齊保單資料",
            text: `${policyMetrics.incompletePolicies} 張保單缺少保單號、保費、保障額度或條款來源。`,
            href: "/policies",
            tone: "amber" as const,
          },
        ]
      : []),
    ...(claimMetrics.followUpClaims > 0
      ? [
          {
            title: "追蹤理賠案件",
            text: `${claimMetrics.followUpClaims} 件理賠已到追蹤日，請確認補件或保險公司審核狀態。`,
            href: "/claims",
            tone: "rose" as const,
          },
        ]
      : []),
    ...(pendingHealthChecks > 0
      ? [
          {
            title: "完成客戶健診",
            text: `${pendingHealthChecks} 位客戶尚未完成保單健診流程。`,
            href: clients[0] ? `/advisor/clients/${clients[0].id}/policy-check` : "/advisor",
            tone: "sky" as const,
          },
        ]
      : []),
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-bold text-amber-700">顧問工作台</p>
          <h1 className="mt-2 text-3xl font-bold text-gray-900">保單健診 CRM</h1>
          <p className="mt-2 text-sm leading-6 text-gray-500">
            從客戶建檔、現有保單整理、健診報告到理賠服務，集中管理業務員每天要追蹤的案件。
          </p>
        </div>
        <Link
          href="/advisor/clients/new"
          className="rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
        >
          + 新增客戶
        </Link>
      </div>

      <div className="mb-6 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {dashboardItems.map((item) => (
          <div key={item.label} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-sm font-medium text-gray-500">{item.label}</p>
            <p className={`mt-2 text-2xl font-bold tabular-nums ${item.tone}`}>{item.value}</p>
          </div>
        ))}
      </div>

      <section className="mb-8 rounded-xl border border-amber-200 bg-amber-50 p-4">
        <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-bold text-amber-900">業務流程</p>
            <h2 className="text-lg font-bold text-amber-950">保單健診要先從既有保單開始</h2>
          </div>
          <span className="text-xs font-bold text-amber-700">第一版先支援手動輸入與報告預覽</span>
        </div>
        <div className="grid gap-3 md:grid-cols-4">
          {workflowItems.map((item, index) => (
            <Link
              key={item.title}
              href={item.href}
              className="rounded-lg border border-amber-200 bg-white p-3 transition hover:border-amber-400 hover:shadow-sm"
            >
              <span className="text-xs font-bold text-amber-600">0{index + 1}</span>
              <p className="mt-1 text-sm font-bold text-gray-900">{item.title}</p>
              <p className="mt-1 text-xs leading-5 text-gray-500">{item.text}</p>
            </Link>
          ))}
        </div>
      </section>

      <section className="mb-8 rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
        <div className="mb-3 flex flex-col gap-1 sm:flex-row sm:items-end sm:justify-between">
          <div>
            <p className="text-sm font-bold text-slate-700">今日待追蹤</p>
            <h2 className="text-lg font-bold text-gray-950">依保單完整度、健診與理賠進度產生待辦</h2>
          </div>
          <span className="text-xs font-bold text-gray-400">{advisorTodos.length || 0} 項待辦</span>
        </div>
        {advisorTodos.length === 0 ? (
          <div className="rounded-lg bg-emerald-50 px-4 py-3 text-sm font-bold text-emerald-800">
            目前沒有急需處理的補件、健診或理賠追蹤。
          </div>
        ) : (
          <div className="grid gap-3 md:grid-cols-3">
            {advisorTodos.map((todo) => (
              <Link
                key={todo.title}
                href={todo.href}
                className={`rounded-lg border p-3 transition hover:shadow-sm ${
                  todo.tone === "rose"
                    ? "border-rose-200 bg-rose-50 hover:border-rose-300"
                    : todo.tone === "sky"
                      ? "border-sky-200 bg-sky-50 hover:border-sky-300"
                      : "border-amber-200 bg-amber-50 hover:border-amber-300"
                }`}
              >
                <p className="text-sm font-bold text-gray-950">{todo.title}</p>
                <p className="mt-1 text-xs leading-5 text-gray-600">{todo.text}</p>
              </Link>
            ))}
          </div>
        )}
        {claimMetrics.cases.length > 0 && (
          <div className="mt-4 overflow-hidden rounded-lg border border-gray-100">
            {claimMetrics.cases.map((claimCase) => (
              <div key={claimCase.id} className="grid grid-cols-[1fr_auto] gap-3 border-t border-gray-100 px-3 py-2 first:border-t-0">
                <div>
                  <p className="text-sm font-bold text-gray-900">{claimCase.owner_name || "未命名客戶"} 理賠案件 #{claimCase.id}</p>
                  <p className="mt-0.5 text-xs text-gray-400">
                    {claimCase.status}・預估 {formatDashboardMoney(claimCase.estimated_total)}
                  </p>
                </div>
                <span className="text-right text-xs font-bold text-gray-500">
                  {claimCase.next_follow_up_date || "未排追蹤"}
                </span>
              </div>
            ))}
          </div>
        )}
      </section>

      <div className="mb-3 flex items-center justify-between">
        <h2 className="text-sm font-bold text-gray-700">客戶清單</h2>
        <span className="text-xs font-medium text-gray-400">共 {clients.length} 位客戶</span>
      </div>

      {loading && <div className="py-16 text-center text-sm text-gray-400">載入中...</div>}

      {error && <div className="rounded-xl border border-red-200 bg-red-50 p-4 text-sm text-red-700">{error}</div>}

      {!loading && !error && clients.length === 0 && (
        <div className="rounded-xl border border-dashed border-gray-200 py-16 text-center">
          <p className="mb-4 text-sm text-gray-400">目前沒有客戶資料</p>
          <Link href="/advisor/clients/new" className="text-sm text-emerald-600 hover:underline">
            新增第一位客戶
          </Link>
        </div>
      )}

      {!loading && clients.length > 0 && (
        <div className="overflow-x-auto rounded-xl border border-gray-200 bg-white">
          <table className="w-full min-w-[840px] table-fixed text-sm">
            <thead className="border-b border-gray-200 bg-gray-50">
              <tr>
                <th className="w-[220px] px-4 py-3 text-left font-medium text-gray-600">姓名</th>
                <th className="w-[90px] px-4 py-3 text-right font-medium text-gray-600">年齡</th>
                <th className="w-[150px] px-4 py-3 text-left font-medium text-gray-600">職業</th>
                <th className="w-[150px] px-4 py-3 text-right font-medium text-gray-600">年可投入保費</th>
                <th className="w-[130px] px-4 py-3 text-left font-medium text-gray-600">狀態</th>
                <th className="w-[180px] px-4 py-3 text-right font-medium text-gray-600">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {clients.map((client) => (
                <tr key={client.id} className="transition-colors hover:bg-gray-50">
                  <td className="px-4 py-3">
                    <Link href={`/advisor/clients/${client.id}`} className="font-medium text-gray-900 hover:text-blue-600">
                      {client.name}
                    </Link>
                    {client.email && <div className="text-xs text-gray-400">{client.email}</div>}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-600">{client.age} 歲</td>
                  <td className="px-4 py-3 text-gray-500">{client.occupation || "待補"}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-500">
                    {client.monthly_investable
                      ? `${(client.monthly_investable * 12).toLocaleString("zh-TW")} 元`
                      : "待補"}
                  </td>
                  <td className="px-4 py-3">
                    <span
                      className={`inline-flex items-center rounded px-2 py-0.5 text-xs font-medium ${
                        STATUS_COLOR[client.status] ?? "bg-gray-100 text-gray-600"
                      }`}
                    >
                      {STATUS_LABEL[client.status] ?? client.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-3">
                      <Link href={`/advisor/clients/${client.id}`} className="text-xs text-blue-500 hover:text-blue-700">
                        客戶 360
                      </Link>
                      <Link
                        href={`/advisor/clients/${client.id}/policy-check`}
                        className="text-xs text-amber-600 hover:text-amber-800"
                      >
                        健診
                      </Link>
                      <button
                        onClick={() => handleDelete(client.id, client.name)}
                        className="text-xs text-red-400 hover:text-red-600"
                        type="button"
                      >
                        刪除
                      </button>
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      )}
    </div>
  );
}
