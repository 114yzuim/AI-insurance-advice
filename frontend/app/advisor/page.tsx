"use client";
import React, { useEffect, useState } from "react";
import Link from "next/link";

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
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch("/api/advisor/clients")
      .then((r) => r.json())
      .then((data) => setClients(Array.isArray(data) ? data : data.items ?? []))
      .catch(() => setError("載入失敗，請確認後端已啟動"))
      .finally(() => setLoading(false));
  }, []);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`確定要刪除「${name}」？此操作無法復原。`)) return;
    await fetch(`/api/advisor/clients/${id}`, { method: "DELETE" });
    setClients((prev) => prev.filter((c) => c.id !== id));
  };

  return (
    <div className="max-w-4xl mx-auto px-4 py-8">
      <div className="flex items-center justify-between mb-8">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">客戶列表</h1>
          <p className="text-gray-500 text-sm mt-1">管理所有客戶的退休規劃資料</p>
        </div>
        <Link
          href="/advisor/clients/new"
          className="bg-emerald-600 hover:bg-emerald-700 text-white text-sm font-medium px-4 py-2.5 rounded-lg transition-colors"
        >
          + 新增客戶
        </Link>
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
        <div className="bg-white border border-gray-200 rounded-xl overflow-hidden">
          <table className="w-full text-sm">
            <thead className="bg-gray-50 border-b border-gray-200">
              <tr>
                <th className="text-left px-4 py-3 font-medium text-gray-600">姓名</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">年齡</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">職業</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">預計退休</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">狀態</th>
                <th className="text-left px-4 py-3 font-medium text-gray-600">操作</th>
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
                  <td className="px-4 py-3 text-gray-600">{c.age} 歲</td>
                  <td className="px-4 py-3 text-gray-500">{c.occupation || "—"}</td>
                  <td className="px-4 py-3 text-gray-500">{c.target_retire_age ? `${c.target_retire_age} 歲` : "—"}</td>
                  <td className="px-4 py-3">
                    <span className={`inline-flex items-center px-2 py-0.5 rounded text-xs font-medium ${STATUS_COLOR[c.status] ?? "bg-gray-100 text-gray-600"}`}>
                      {STATUS_LABEL[c.status] ?? c.status}
                    </span>
                  </td>
                  <td className="px-4 py-3">
                    <div className="flex items-center gap-3">
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
