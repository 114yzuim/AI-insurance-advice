"use client";
import React, { useState } from "react";
import { AllocationStrategy } from "@/components/allocation/AllocationStrategy";
import AccumulationChart from "@/components/allocation/AccumulationChart";
import { toAccPoints } from "@/components/allocation/chart-adapters";
import type { AccPoint } from "@/components/allocation/chart-types";
import "@/components/allocation/styles.css";
import type { ClientInputs, RiskTolerance } from "@/components/allocation/types";
import type { ViewModel } from "@/components/allocation/AllocationStrategy";

interface FormState {
  age: string;
  retireAge: string;
  monthlyInvestable: string;
  dependents: string;
  riskTolerance: RiskTolerance;
  hasMedicalCoverage: boolean;
  hasLifeCoverage: boolean;
  currentAssets: string;
  targetMonthlyExpense: string;
}

const DEFAULT_FORM: FormState = {
  age: "",
  retireAge: "",
  monthlyInvestable: "",
  dependents: "0",
  riskTolerance: "mid",
  hasMedicalCoverage: false,
  hasLifeCoverage: false,
  currentAssets: "",
  targetMonthlyExpense: "",
};

// A/B/C category assumed annual rates (from engine/constants.py)
const CATEGORY_RATES = { A: 0.06, B: 0.022, C: 0.0 };

export default function AllocationPage() {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [submitted, setSubmitted] = useState<ClientInputs | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

  const [chartData, setChartData] = useState<AccPoint[] | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);
  const [chartRetireAge, setChartRetireAge] = useState(65);
  const [achievementRatio, setAchievementRatio] = useState<number | null>(null);
  const [affordableMonthly, setAffordableMonthly] = useState<number | null>(null);

  function handleSubmit(e: React.FormEvent) {
    e.preventDefault();
    const age = parseInt(form.age);
    const retireAge = parseInt(form.retireAge);
    if (!form.age || !form.retireAge || isNaN(age) || isNaN(retireAge)) {
      setFormError("請填寫年齡與退休年齡。");
      return;
    }
    if (retireAge <= age) {
      setFormError("退休年齡必須大於目前年齡。");
      return;
    }
    setFormError(null);
    setChartData(null);
    setChartError(null);
    setSubmitted({
      age,
      retireAge,
      monthlyInvestable: form.monthlyInvestable ? parseFloat(form.monthlyInvestable) : 0,
      dependents: parseInt(form.dependents) || 0,
      riskTolerance: form.riskTolerance,
      hasMedicalCoverage: form.hasMedicalCoverage,
      hasLifeCoverage: form.hasLifeCoverage,
    });
  }

  async function handleAllocationNext(view: ViewModel) {
    if (!submitted) return;
    setChartLoading(true);
    setChartError(null);
    setChartData(null);

    const { a, b, c } = view.allocation;
    const blendedRate = (a * CATEGORY_RATES.A + b * CATEGORY_RATES.B + c * CATEGORY_RATES.C) / 100;

    try {
      const res = await fetch("/api/simulator/forward", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_age: submitted.age,
          retire_age: submitted.retireAge,
          life_expectancy: 85,
          current_assets_twd: (parseFloat(form.currentAssets) || 0) * 10000,
          monthly_saving_twd: submitted.monthlyInvestable || 0,
          target_monthly_expense_twd: parseFloat(form.targetMonthlyExpense) || 40000,
          annual_rate: blendedRate,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setChartError(data.detail || "試算失敗，請稍後再試。");
        return;
      }
      setChartData(toAccPoints(data.result.yearly_assets));
      setChartRetireAge(submitted.retireAge);
      setAchievementRatio(data.result.achievement_ratio);
      setAffordableMonthly(data.result.affordable_monthly_withdrawal_twd);
    } catch {
      setChartError("試算失敗，請稍後再試。");
    } finally {
      setChartLoading(false);
    }
  }

  const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400";
  const labelCls = "block text-sm font-medium text-gray-700 mb-1";

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">退休規劃</h1>
        <p className="text-gray-500 text-sm">
          填入基本資料，AI 幫您建議儲蓄投資、保險保障、醫療長照三類的理想比例。
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white border border-gray-200 rounded-xl p-6 mb-8 space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>目前年齡 *</label>
            <input
              type="number" className={inputCls} placeholder="例：35"
              value={form.age} min={1} max={100}
              onChange={(e) => setForm((f) => ({ ...f, age: e.target.value }))}
            />
          </div>
          <div>
            <label className={labelCls}>預計退休年齡 *</label>
            <input
              type="number" className={inputCls} placeholder="例：65"
              value={form.retireAge} min={1} max={120}
              onChange={(e) => setForm((f) => ({ ...f, retireAge: e.target.value }))}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>每月可投入（元，選填）</label>
            <input
              type="number" className={inputCls} placeholder="例：10000"
              value={form.monthlyInvestable} min={0}
              onChange={(e) => setForm((f) => ({ ...f, monthlyInvestable: e.target.value }))}
            />
          </div>
          <div>
            <label className={labelCls}>扶養人數</label>
            <input
              type="number" className={inputCls}
              value={form.dependents} min={0}
              onChange={(e) => setForm((f) => ({ ...f, dependents: e.target.value }))}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>目前已有資產（萬元，選填）</label>
            <input
              type="number" className={inputCls} placeholder="例：100"
              value={form.currentAssets} min={0}
              onChange={(e) => setForm((f) => ({ ...f, currentAssets: e.target.value }))}
            />
          </div>
          <div>
            <label className={labelCls}>退休後每月目標支出（元，選填）</label>
            <input
              type="number" className={inputCls} placeholder="例：40000"
              value={form.targetMonthlyExpense} min={0}
              onChange={(e) => setForm((f) => ({ ...f, targetMonthlyExpense: e.target.value }))}
            />
          </div>
        </div>

        <div>
          <label className={labelCls}>風險偏好</label>
          <div className="flex gap-3">
            {(["low", "mid", "high"] as RiskTolerance[]).map((r) => {
              const labels = { low: "低", mid: "中", high: "高" };
              return (
                <button
                  key={r} type="button"
                  onClick={() => setForm((f) => ({ ...f, riskTolerance: r }))}
                  className={`flex-1 py-2 rounded-lg border text-sm font-medium transition-colors ${
                    form.riskTolerance === r
                      ? "bg-blue-600 text-white border-blue-600"
                      : "bg-white text-gray-600 border-gray-300 hover:border-blue-400"
                  }`}
                >
                  {labels[r]}
                </button>
              );
            })}
          </div>
        </div>

        <div className="flex gap-6">
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox" checked={form.hasMedicalCoverage} className="rounded"
              onChange={(e) => setForm((f) => ({ ...f, hasMedicalCoverage: e.target.checked }))}
            />
            已有醫療險
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox" checked={form.hasLifeCoverage} className="rounded"
              onChange={(e) => setForm((f) => ({ ...f, hasLifeCoverage: e.target.checked }))}
            />
            已有壽險
          </label>
        </div>

        {formError && <p className="text-red-600 text-sm">{formError}</p>}

        <button
          type="submit"
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
        >
          開始估算
        </button>
      </form>

      {submitted && (
        <div className="mb-8">
          <AllocationStrategy
            client={submitted}
            baseUrl="/api/allocation"
            onNext={handleAllocationNext}
          />
        </div>
      )}

      {/* Trend chart section */}
      {(chartLoading || chartData || chartError) && (
        <div className="bg-white border border-gray-200 rounded-xl p-6 mb-8">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">退休資產規劃曲線</h2>
          <p className="text-xs text-gray-400 mb-4">
            依據您的 A/B/C 配置比例，以各類別假設報酬率加權計算，非保險公司正式建議書。
          </p>

          {chartLoading && (
            <div className="flex items-center justify-center py-12 gap-3 text-gray-400 text-sm">
              <span className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin inline-block" />
              試算中…
            </div>
          )}

          {chartError && (
            <p className="text-red-500 text-sm py-6 text-center">{chartError}</p>
          )}

          {chartData && (
            <>
              {achievementRatio !== null && (
                <div className="flex gap-6 mb-4">
                  <div className="text-center">
                    <div className={`text-2xl font-bold ${achievementRatio >= 1 ? "text-green-600" : "text-amber-500"}`}>
                      {Math.round(achievementRatio * 100)}%
                    </div>
                    <div className="text-xs text-gray-400 mt-0.5">退休目標達成率</div>
                  </div>
                  {affordableMonthly !== null && (
                    <div className="text-center">
                      <div className="text-2xl font-bold text-gray-700">
                        {Math.round(affordableMonthly / 1000)}K
                      </div>
                      <div className="text-xs text-gray-400 mt-0.5">退休後可月領（元）</div>
                    </div>
                  )}
                </div>
              )}
              <AccumulationChart data={chartData} retireAge={chartRetireAge} />
              <p className="text-xs text-gray-400 mt-3">
                本試算為概念性數字，非保險公司正式建議書。所有報酬率為假設值，實際結果會受市場、通膨、健康變化影響。
              </p>
            </>
          )}
        </div>
      )}

      <footer className="text-xs text-gray-400 border-t border-gray-100 pt-4 text-center">
        本工具提供配置參考，非正式保險建議，請諮詢合格業務員。
      </footer>
    </div>
  );
}
