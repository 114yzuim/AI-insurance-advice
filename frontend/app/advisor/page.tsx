"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import {
  DEMO_POLICIES,
  fetchPolicyPortfolio,
  getPolicySummary,
  type PolicySummary,
} from "@/lib/demo-policies";

interface Client {
  id: number;
  name: string;
  age: number;
  occupation: string | null;
  status: string;
  email: string | null;
  target_retire_age: number | null;
  monthly_investable: number | null;
  created_at: string;
}

const STATUS_LABEL: Record<string, string> = {
  new: "新建檔",
  questionnaire_done: "問卷完成",
};

const STATUS_COLOR: Record<string, string> = {
  new: "bg-gray-100 text-gray-600",
  questionnaire_done: "bg-green-100 text-green-700",
};

export default function AdvisorPage() {
  const [clients, setClients] = useState<Client[]>([]);
  const [policySummary, setPolicySummary] = useState<PolicySummary>(() => getPolicySummary(DEMO_POLICIES));
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/advisor/clients")
      .then((r) => r.json())
      .then((data) => setClients(Array.isArray(data) ? data : data.items ?? []))
      .catch(() => setError("載入失敗，請確認後端已啟動"))
      .finally(() => setLoading(false));

    fetchPolicyPortfolio()
      .then((data) => setPolicySummary(data.summary))
      .catch(() => setPolicySummary(getPolicySummary(DEMO_POLICIES)));
  }, []);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`確定要刪除「${name}」？此操作無法復原。`)) return;
    await fetch(`/api/advisor/clients/${id}`, { method: "DELETE" });
    setClients((prev) => prev.filter((c) => c.id !== id));
  };

  const dashboardItems = [
    { label: "客戶", value: `${clients.length || 126} 人`, tone: "text-slate-950" },
    { label: "保單總數", value: `${policySummary.policyCount} 張`, tone: "text-teal-700" },
    { label: "本月待處理理賠", value: "8 件", tone: "text-rose-600" },
    { label: "待完成健診", value: `${clients.length ? Math.max(1, Math.ceil(clients.length * 0.35)) : 17} 人`, tone: "text-amber-600" },
    { label: "保單資料不完整", value: `${policySummary.incomplete} 張`, tone: "text-sky-700" },
    { label: "近期需要追蹤", value: "12 人", tone: "text-violet-700" },
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
          className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors"
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
        <h2 className="text-sm font-bold text-gray-700">客戶列表</h2>
        <span className="text-xs font-medium text-gray-400">依建檔時間排序</span>
      </div>

      {loading && (
        <div className="text-center py-16 text-gray-400 text-sm">載入中…</div>
      )}

      {error && (
        <div className="bg-red-50 border border-red-200 rounded-xl p-4 text-red-700 text-sm">
          {error}
        </div>
      )}

      {!loading && !error && clients.length === 0 && (
        <div className="text-center py-16 border border-dashed border-gray-200 rounded-xl">
          <p className="text-gray-400 text-sm mb-4">尚無客戶資料</p>
          <Link
            href="/advisor/clients/new"
            className="text-emerald-600 hover:underline text-sm"
          >
            新增第一位客戶 →
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
                <th className="w-[150px] px-4 py-3 text-right font-medium text-gray-600">年繳保費</th>
                <th className="w-[130px] px-4 py-3 text-left font-medium text-gray-600">狀態</th>
                <th className="w-[130px] px-4 py-3 text-right font-medium text-gray-600">操作</th>
              </tr>
            </thead>
            <tbody className="divide-y divide-gray-100">
              {clients.map((c) => (
                <tr key={c.id} className="hover:bg-gray-50 transition-colors">
                  <td className="px-4 py-3">
                    <Link href={`/advisor/clients/${c.id}`} className="font-medium text-gray-900 hover:text-blue-600">
                      {c.name}
                    </Link>
                    {c.email && <div className="text-xs text-gray-400">{c.email}</div>}
                  </td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-600">{c.age} 歲</td>
                  <td className="px-4 py-3 text-gray-500">{c.occupation || "—"}</td>
                  <td className="px-4 py-3 text-right tabular-nums text-gray-500">
                    {c.monthly_investable ? `${(c.monthly_investable * 12).toLocaleString("zh-TW")} 元` : "待補"}
                  </td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLOR[c.status] ?? "bg-gray-100 text-gray-600"}`}>
                      {STATUS_LABEL[c.status] ?? c.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center justify-end gap-3">
                      <Link href={`/advisor/clients/${c.id}`} className="text-blue-500 hover:text-blue-700 text-xs">
                        查看
                      </Link>
                      <Link href={`/advisor/clients/${c.id}/edit`} className="text-emerald-500 hover:text-emerald-700 text-xs">
                        編輯
                      </Link>
                      <button
                        onClick={() => handleDelete(c.id, c.name)}
                        className="text-red-400 hover:text-red-600 text-xs"
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
