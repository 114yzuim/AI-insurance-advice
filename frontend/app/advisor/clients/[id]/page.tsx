"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

interface Client {
  id: number;
  name: string;
  age: number;
  email: string | null;
  phone: string | null;
  gender: string | null;
  occupation: string | null;
  target_retire_age: number | null;
  life_expectancy: number | null;
  risk_tolerance: string | null;
  status: string;
  monthly_investable: number | null;
  target_retire_monthly_expense: number | null;
  current_assets: number | null;
  monthly_income: number | null;
  monthly_expense: number | null;
}

const GENDER: Record<string, string> = { M: "男", F: "女" };
const STATUS_LABEL: Record<string, string> = { new: "新建檔", questionnaire_done: "問卷完成" };

function fmt(n: number | null | undefined): string {
  if (n == null) return "—";
  return n.toLocaleString("zh-TW");
}

export default function ClientHubPage() {
  const { id } = useParams<{ id: string }>();
  const [client, setClient] = useState<Client | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/advisor/clients/${id}`)
      .then((r) => {
        if (!r.ok) throw new Error("not found");
        return r.json();
      })
      .then(setClient)
      .catch(() => setError("找不到此客戶"))
      .finally(() => setLoading(false));
  }, [id]);

  if (loading) return <div className="text-center py-16 text-gray-400 text-sm">載入中…</div>;
  if (error || !client) return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <p className="text-red-500 text-sm">{error}</p>
      <Link href="/advisor" className="text-blue-500 text-sm">← 返回列表</Link>
    </div>
  );

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="mb-6">
        <Link href="/advisor" className="text-sm text-gray-400 hover:text-gray-600">← 客戶列表</Link>
        <div className="flex items-center justify-between mt-2">
          <h1 className="text-2xl font-bold text-gray-900">{client.name}</h1>
          <span className="text-xs bg-gray-100 text-gray-600 px-2 py-1 rounded-lg">
            {STATUS_LABEL[client.status] ?? client.status}
          </span>
        </div>
      </div>

      {/* Basic info card */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-4">
        <h2 className="font-semibold text-gray-700 mb-4 text-sm uppercase tracking-wide">基本資料</h2>
        <div className="grid grid-cols-3 gap-4 text-sm">
          <div><span className="text-gray-400">年齡</span><div className="font-medium text-gray-800 mt-0.5">{client.age} 歲</div></div>
          <div><span className="text-gray-400">性別</span><div className="font-medium text-gray-800 mt-0.5">{GENDER[client.gender ?? ""] ?? "—"}</div></div>
          <div><span className="text-gray-400">職業</span><div className="font-medium text-gray-800 mt-0.5">{client.occupation || "—"}</div></div>
          <div><span className="text-gray-400">電話</span><div className="font-medium text-gray-800 mt-0.5">{client.phone || "—"}</div></div>
          <div><span className="text-gray-400">Email</span><div className="font-medium text-gray-800 mt-0.5">{client.email || "—"}</div></div>
          <div><span className="text-gray-400">預計退休</span><div className="font-medium text-gray-800 mt-0.5">{client.target_retire_age ? `${client.target_retire_age} 歲` : "—"}</div></div>
        </div>
      </div>

      {/* Financial summary */}
      <div className="bg-white border border-gray-200 rounded-xl p-6 mb-6">
        <h2 className="font-semibold text-gray-700 mb-4 text-sm uppercase tracking-wide">財務摘要</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">月收入</div>
            <div className="font-semibold text-gray-800">{fmt(client.monthly_income)} 元</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">月支出</div>
            <div className="font-semibold text-gray-800">{fmt(client.monthly_expense)} 元</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">現有資產</div>
            <div className="font-semibold text-gray-800">{fmt(client.current_assets)} 元</div>
          </div>
          <div className="bg-gray-50 rounded-lg p-3">
            <div className="text-gray-400 text-xs mb-1">每月可投入</div>
            <div className="font-semibold text-gray-800">{fmt(client.monthly_investable)} 元</div>
          </div>
        </div>
      </div>

      {/* Action cards */}
      <h2 className="font-semibold text-gray-700 mb-3 text-sm">規劃流程</h2>
      <div className="grid grid-cols-1 gap-3">
        <Link href={`/advisor/clients/${id}/balance-sheet`}
          className="bg-white border border-gray-200 hover:border-blue-300 rounded-xl p-5 flex items-center justify-between group transition-colors">
          <div>
            <div className="font-medium text-gray-800">資產負債表</div>
            <div className="text-xs text-gray-400 mt-0.5">填寫資產與負債的詳細項目</div>
          </div>
          <span className="text-blue-400 group-hover:translate-x-1 transition-transform">→</span>
        </Link>

        <Link href={`/advisor/clients/${id}/questionnaire`}
          className="bg-white border border-gray-200 hover:border-blue-300 rounded-xl p-5 flex items-center justify-between group transition-colors">
          <div>
            <div className="font-medium text-gray-800">退休規劃問卷</div>
            <div className="text-xs text-gray-400 mt-0.5">了解客戶的退休目標與風險偏好</div>
          </div>
          <span className="text-blue-400 group-hover:translate-x-1 transition-transform">→</span>
        </Link>

        <Link href={`/advisor/clients/${id}/retirement`}
          className="bg-white border border-gray-200 hover:border-blue-300 rounded-xl p-5 flex items-center justify-between group transition-colors">
          <div>
            <div className="font-medium text-gray-800">退休規劃試算</div>
            <div className="text-xs text-gray-400 mt-0.5">A/B/C 配置比例與資產曲線試算，直接套用客戶資料</div>
          </div>
          <span className="text-blue-400 group-hover:translate-x-1 transition-transform">→</span>
        </Link>
      </div>
    </div>
  );
}
