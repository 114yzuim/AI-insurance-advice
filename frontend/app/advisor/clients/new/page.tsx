"use client";
import React, { useState } from "react";
import { useRouter } from "next/navigation";
import Link from "next/link";

interface FormState {
  name: string;
  age: string;
  email: string;
  phone: string;
  gender: string;
  occupation: string;
  target_retire_age: string;
  life_expectancy: string;
  risk_tolerance: string;
  planning_goals: string[];
  selected_modules: string[];
}

const DEFAULT: FormState = {
  name: "", age: "", email: "", phone: "", gender: "", occupation: "",
  target_retire_age: "65", life_expectancy: "85", risk_tolerance: "medium",
  planning_goals: [], selected_modules: ["A", "B", "C"],
};

const PLANNING_GOALS = [
  { key: "純保障", sub: "高槓桿壽險" },
  { key: "資產儲蓄", sub: "重內部報酬率" },
  { key: "財富傳承", sub: "預留稅源" },
  { key: "醫療照護", sub: "長照／醫療" },
];

const MODULES = [
  { key: "A", label: "投資", sub: "ETF・股債", icon: "↗" },
  { key: "B", label: "保險", sub: "年金・壽險", icon: "🛡" },
  { key: "C", label: "失能長照", sub: "失能扶助・長照險", icon: "♡" },
];

const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-emerald-400";
const labelCls = "block text-sm font-medium text-gray-700 mb-1";

export default function NewClientPage() {
  const router = useRouter();
  const [form, setForm] = useState<FormState>(DEFAULT);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const set = (k: keyof FormState, v: string) => setForm((f) => ({ ...f, [k]: v }));

  const toggleGoal = (goal: string) =>
    setForm((f) => ({
      ...f,
      planning_goals: f.planning_goals.includes(goal)
        ? f.planning_goals.filter((g) => g !== goal)
        : [...f.planning_goals, goal],
    }));

  const toggleModule = (mod: string) =>
    setForm((f) => {
      const next = f.selected_modules.includes(mod)
        ? f.selected_modules.filter((m) => m !== mod)
        : [...f.selected_modules, mod];
      return { ...f, selected_modules: next.length > 0 ? next : f.selected_modules };
    });

  // Real-time computed
  const age = parseInt(form.age) || 0;
  const retireAge = parseInt(form.target_retire_age) || 0;
  const lifeExp = parseInt(form.life_expectancy) || 0;
  const yearsToRetire = retireAge > age ? retireAge - age : null;
  const retirementYears = lifeExp > retireAge ? lifeExp - retireAge : null;
  const totalYears = lifeExp > age ? lifeExp - age : null;

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!form.name.trim() || !form.age) { setError("請填寫姓名與年齡。"); return; }
    setSaving(true); setError(null);
    try {
      const res = await fetch("/api/advisor/clients", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          name: form.name.trim(), age: parseInt(form.age),
          email: form.email || null, phone: form.phone || null,
          gender: form.gender || null, occupation: form.occupation || null,
          target_retire_age: retireAge || 65, life_expectancy: lifeExp || 85,
          risk_tolerance: form.risk_tolerance || null,
          planning_goals: form.planning_goals,
          selected_modules: form.selected_modules.length > 0 ? form.selected_modules : ["A", "B", "C"],
        }),
      });
      const data = await res.json();
      if (!res.ok) { setError(data.detail || "建立失敗"); return; }
      router.push(`/advisor/clients/${data.id}`);
    } catch { setError("建立失敗，請稍後再試。"); } finally { setSaving(false); }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-6">
        <Link href="/advisor" className="text-sm text-gray-400 hover:text-gray-600">← 返回客戶列表</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">新增客戶</h1>
      </div>

      <form onSubmit={handleSubmit} className="space-y-6">
        {/* 01 基本資料 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-gray-400">01</span>
            <h2 className="font-semibold text-gray-800">基本資料</h2>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div className="col-span-2">
              <label className={labelCls}>姓名 *</label>
              <input type="text" className={inputCls} placeholder="王小明" value={form.name} onChange={(e) => set("name", e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>年齡 *</label>
              <input type="number" className={inputCls} placeholder="35" min={1} max={120} value={form.age} onChange={(e) => set("age", e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>性別</label>
              <select className={inputCls} value={form.gender} onChange={(e) => set("gender", e.target.value)}>
                <option value="">請選擇</option>
                <option value="M">男</option>
                <option value="F">女</option>
              </select>
            </div>
            <div>
              <label className={labelCls}>Email</label>
              <input type="email" className={inputCls} placeholder="example@email.com" value={form.email} onChange={(e) => set("email", e.target.value)} />
            </div>
            <div>
              <label className={labelCls}>電話</label>
              <input type="text" className={inputCls} placeholder="0912-345-678" value={form.phone} onChange={(e) => set("phone", e.target.value)} />
            </div>
            <div className="col-span-2">
              <label className={labelCls}>職業</label>
              <input type="text" className={inputCls} placeholder="工程師" value={form.occupation} onChange={(e) => set("occupation", e.target.value)} />
            </div>
          </div>
        </div>

        {/* 02 退休目標 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-4">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-gray-400">02</span>
            <h2 className="font-semibold text-gray-800">退休目標</h2>
          </div>
          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className={labelCls}>預計退休年齡</label>
              <div className="relative">
                <input type="number" className={inputCls} min={30} max={100} value={form.target_retire_age} onChange={(e) => set("target_retire_age", e.target.value)} />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 pointer-events-none">歲</span>
              </div>
            </div>
            <div>
              <label className={labelCls}>預估平均餘命</label>
              <div className="relative">
                <input type="number" className={inputCls} min={50} max={120} value={form.life_expectancy} onChange={(e) => set("life_expectancy", e.target.value)} />
                <span className="absolute right-3 top-1/2 -translate-y-1/2 text-xs text-gray-400 pointer-events-none">歲</span>
              </div>
            </div>
            <div className="col-span-2">
              <label className={labelCls}>可承受單年最大跌幅</label>
              <select className={inputCls} value={form.risk_tolerance} onChange={(e) => set("risk_tolerance", e.target.value)}>
                <option value="">請選擇</option>
                <option value="low">低（可承受 -10% 以內）</option>
                <option value="medium">中（可承受 -10% ~ -30%）</option>
                <option value="high">高（可承受 -30% 以上）</option>
              </select>
            </div>
          </div>

          {/* Computed preview */}
          {(yearsToRetire !== null || retirementYears !== null || totalYears !== null) && (
            <div className="grid grid-cols-3 gap-3 mt-2">
              {[["距退休", yearsToRetire], ["退休生活", retirementYears], ["預估餘命", totalYears]].map(([label, val]) => (
                <div key={label as string} className="bg-gray-50 rounded-xl p-3 text-center">
                  <div className="text-2xl font-bold text-gray-800">
                    {val !== null ? val : "—"}
                    {val !== null && <span className="text-sm font-normal ml-0.5">年</span>}
                  </div>
                  <div className="text-xs text-gray-400 mt-0.5">{label}</div>
                </div>
              ))}
            </div>
          )}

          {/* Planning goals */}
          <div>
            <label className="block text-sm font-medium text-gray-700 mb-2">
              規劃目標 <span className="text-xs text-gray-400 font-normal">・可複選</span>
            </label>
            <div className="grid grid-cols-2 gap-2">
              {PLANNING_GOALS.map(({ key, sub }) => {
                const selected = form.planning_goals.includes(key);
                return (
                  <button key={key} type="button" onClick={() => toggleGoal(key)}
                    className={`rounded-xl border p-3 text-left transition-colors ${selected ? "border-emerald-500 bg-emerald-50" : "border-gray-200 bg-white hover:border-emerald-300"}`}>
                    <div className={`text-sm font-medium ${selected ? "text-emerald-700" : "text-gray-800"}`}>{key}</div>
                    <div className="text-xs text-gray-400 mt-0.5">{sub}</div>
                  </button>
                );
              })}
            </div>
          </div>
        </div>

        {/* 03 規劃模組 */}
        <div className="bg-white border border-gray-200 rounded-xl p-6 space-y-3">
          <div className="flex items-center gap-2 mb-1">
            <span className="font-mono text-xs text-gray-400">03</span>
            <h2 className="font-semibold text-gray-800">規劃模組</h2>
          </div>
          <p className="text-xs text-gray-400">決定推演器與個別模組顯示的內容。可複選，至少保留一個。</p>
          <div className="grid grid-cols-3 gap-3">
            {MODULES.map(({ key, label, sub, icon }) => {
              const selected = form.selected_modules.includes(key);
              return (
                <button key={key} type="button" onClick={() => toggleModule(key)}
                  className={`relative rounded-xl border p-4 text-left transition-colors ${selected ? "border-emerald-500 bg-emerald-50" : "border-gray-200 bg-white hover:border-emerald-300"}`}>
                  <div className="flex items-center justify-between mb-2">
                    <div className={`w-5 h-5 rounded-full border-2 flex items-center justify-center ${selected ? "border-emerald-600 bg-emerald-600" : "border-gray-300"}`}>
                      {selected && <svg className="w-3 h-3 text-white" fill="none" viewBox="0 0 24 24" stroke="currentColor"><path strokeLinecap="round" strokeLinejoin="round" strokeWidth={3} d="M5 13l4 4L19 7" /></svg>}
                    </div>
                    <span className="text-lg">{icon}</span>
                  </div>
                  <div className="text-xs text-gray-400 font-mono">{key}</div>
                  <div className={`text-sm font-bold mt-0.5 ${selected ? "text-emerald-700" : "text-gray-800"}`}>{label}</div>
                  <div className="text-xs text-gray-400 mt-0.5">{sub}</div>
                </button>
              );
            })}
          </div>
        </div>

        {error && <p className="text-red-600 text-sm">{error}</p>}

        <div className="flex gap-3">
          <Link href="/advisor" className="flex-1 py-2.5 rounded-lg border border-gray-300 text-sm text-center text-gray-600 hover:bg-gray-50 transition-colors">
            取消
          </Link>
          <button type="submit" disabled={saving}
            className="flex-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition-colors">
            {saving ? "建立中…" : "建立客戶"}
          </button>
        </div>
      </form>
    </div>
  );
}
