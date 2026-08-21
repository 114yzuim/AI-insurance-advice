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

interface PolicyRecord {
  id?: number | string;
  policy_no?: string | null;
  policyNo?: string | null;
  company_name?: string | null;
  companyName?: string | null;
  policy_name?: string | null;
  productName?: string | null;
  annual_premium?: number | null;
  annualPremium?: number | null;
}

interface PolicyMetrics {
  policyCount: number;
  incompletePolicies: number;
}

const EMPTY_POLICY_METRICS: PolicyMetrics = {
  policyCount: 0,
  incompletePolicies: 0,
};

const STATUS_LABEL: Record<string, string> = {
  new: "新客戶",
  questionnaire_done: "健診完成",
};

const STATUS_COLOR: Record<string, string> = {
  new: "bg-gray-100 text-gray-600",
  questionnaire_done: "bg-green-100 text-green-700",
};

function hasValue(value: unknown) {
  return typeof value === "string" ? value.trim().length > 0 : value !== null && value !== undefined;
}

function isPolicyIncomplete(policy: PolicyRecord) {
  const policyNo = policy.policy_no ?? policy.policyNo;
  const companyName = policy.company_name ?? policy.companyName;
  const policyName = policy.policy_name ?? policy.productName;
  const annualPremium = Number(policy.annual_premium ?? policy.annualPremium ?? 0);

  return !hasValue(policyNo) || !hasValue(companyName) || !hasValue(policyName) || annualPremium <= 0;
}

async function fetchPolicyMetrics(): Promise<PolicyMetrics> {
  const res = await fetch("/api/policies?profile_id=demo-user", { cache: "no-store" });

  if (!res.ok) {
    throw new Error("Failed to load policies");
  }

  const data = await res.json();
  const policies: PolicyRecord[] = Array.isArray(data?.policies) ? data.policies : [];

  return {
    policyCount: policies.length,
    incompletePolicies: policies.filter(isPolicyIncomplete).length,
  };
}

export default function AdvisorPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [policyMetrics, setPolicyMetrics] = useState<PolicyMetrics>(EMPTY_POLICY_METRICS);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    let isMounted = true;

    async function loadDashboard() {
      try {
        const [clientsRes, metrics] = await Promise.all([
          fetch("/api/advisor/clients", { cache: "no-store" }),
          fetchPolicyMetrics().catch(() => EMPTY_POLICY_METRICS),
        ]);

        if (!clientsRes.ok) {
          throw new Error("Failed to load clients");
        }

        const clientsData = await clientsRes.json();

        if (!isMounted) return;

        setClients(Array.isArray(clientsData) ? clientsData : clientsData.items ?? []);
        setPolicyMetrics(metrics);
      } catch {
        if (isMounted) {
          setError("資料載入失敗，請稍後再試。");
          setPolicyMetrics(EMPTY_POLICY_METRICS);
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
    { label: "本月待處理理賠", value: "0 件", tone: "text-rose-600" },
    { label: "待完成健診", value: `${pendingHealthChecks} 人`, tone: "text-amber-600" },
    { label: "保單資料不完整", value: `${policyMetrics.incompletePolicies} 張`, tone: "text-sky-700" },
    { label: "近期需要追蹤", value: "0 人", tone: "text-violet-700" },
  ];

  return (
    <div className="mx-auto max-w-6xl px-4 py-8">
      <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
        <div>
          <p className="text-sm font-bold text-amber-700">顧問工作台</p>
          <h1 className="mt-2 text-3xl font-bold text-gray-900">客戶保險管理 CRM</h1>
          <p className="mt-2 text-sm leading-6 text-gray-500">
            管理客戶的保單、保障健診與理賠紀錄，優先處理需要追蹤的案件。
          </p>
        </div>
        <Link
          href="/advisor/clients/new"
          className="rounded-lg bg-emerald-600 px-4 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700"
        >
          + 新增客戶
        </Link>
      </div>

      <div className="mb-8 grid gap-3 sm:grid-cols-2 lg:grid-cols-3">
        {dashboardItems.map((item) => (
          <div key={item.label} className="rounded-xl border border-gray-200 bg-white p-4 shadow-sm">
            <p className="text-sm font-medium text-gray-500">{item.label}</p>
            <p className={`mt-2 text-2xl font-bold ${item.tone}`}>{item.value}</p>
          </div>
        ))}
      </div>

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
          <table className="w-full min-w-[760px] table-fixed text-sm">
            <thead className="border-b border-gray-200 bg-gray-50">
              <tr>
                <th className="w-[220px] px-4 py-3 text-left font-medium text-gray-600">姓名</th>
                <th className="w-[90px] px-4 py-3 text-right font-medium text-gray-600">年齡</th>
                <th className="w-[150px] px-4 py-3 text-left font-medium text-gray-600">職業</th>
                <th className="w-[150px] px-4 py-3 text-right font-medium text-gray-600">年可投入保費</th>
                <th className="w-[130px] px-4 py-3 text-left font-medium text-gray-600">狀態</th>
                <th className="w-[130px] px-4 py-3 text-right font-medium text-gray-600">操作</th>
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
                        查看
                      </Link>
                      <Link
                        href={`/advisor/clients/${client.id}/edit`}
                        className="text-xs text-emerald-500 hover:text-emerald-700"
                      >
                        編輯
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
