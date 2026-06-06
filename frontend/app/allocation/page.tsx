"use client";
import React, { useState } from "react";
import { AllocationStrategy } from "@/components/allocation/AllocationStrategy";
import "@/components/allocation/styles.css";
import type { ClientInputs, RiskTolerance } from "@/components/allocation/types";

interface FormState {
  age: string;
  retireAge: string;
  monthlyInvestable: string;
  dependents: string;
  riskTolerance: RiskTolerance;
  hasMedicalCoverage: boolean;
  hasLifeCoverage: boolean;
}

const DEFAULT_FORM: FormState = {
  age: "",
  retireAge: "",
  monthlyInvestable: "",
  dependents: "0",
  riskTolerance: "mid",
  hasMedicalCoverage: false,
  hasLifeCoverage: false,
};

export default function AllocationPage() {
  const [form, setForm] = useState<FormState>(DEFAULT_FORM);
  const [submitted, setSubmitted] = useState<ClientInputs | null>(null);
  const [formError, setFormError] = useState<string | null>(null);

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

  const inputCls = "w-full border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-400";
  const labelCls = "block text-sm font-medium text-gray-700 mb-1";

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="mb-8">
        <h1 className="text-2xl font-bold text-gray-900 mb-1">配置建議</h1>
        <p className="text-gray-500 text-sm">
          根據您的基本資料，系統將估算金融、保險、醫療三桶的配置比例。
        </p>
      </div>

      <form onSubmit={handleSubmit} className="bg-white border border-gray-200 rounded-xl p-6 mb-8 space-y-5">
        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>目前年齡 *</label>
            <input
              type="number"
              className={inputCls}
              placeholder="例：35"
              value={form.age}
              min={1}
              max={100}
              onChange={(e) => setForm((f) => ({ ...f, age: e.target.value }))}
            />
          </div>
          <div>
            <label className={labelCls}>預計退休年齡 *</label>
            <input
              type="number"
              className={inputCls}
              placeholder="例：65"
              value={form.retireAge}
              min={1}
              max={120}
              onChange={(e) => setForm((f) => ({ ...f, retireAge: e.target.value }))}
            />
          </div>
        </div>

        <div className="grid grid-cols-2 gap-4">
          <div>
            <label className={labelCls}>每月可投入（元，選填）</label>
            <input
              type="number"
              className={inputCls}
              placeholder="例：10000"
              value={form.monthlyInvestable}
              min={0}
              onChange={(e) => setForm((f) => ({ ...f, monthlyInvestable: e.target.value }))}
            />
          </div>
          <div>
            <label className={labelCls}>扶養人數</label>
            <input
              type="number"
              className={inputCls}
              value={form.dependents}
              min={0}
              onChange={(e) => setForm((f) => ({ ...f, dependents: e.target.value }))}
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
                  key={r}
                  type="button"
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
              type="checkbox"
              checked={form.hasMedicalCoverage}
              onChange={(e) => setForm((f) => ({ ...f, hasMedicalCoverage: e.target.checked }))}
              className="rounded"
            />
            已有醫療險
          </label>
          <label className="flex items-center gap-2 text-sm text-gray-700 cursor-pointer">
            <input
              type="checkbox"
              checked={form.hasLifeCoverage}
              onChange={(e) => setForm((f) => ({ ...f, hasLifeCoverage: e.target.checked }))}
              className="rounded"
            />
            已有壽險
          </label>
        </div>

        {formError && (
          <p className="text-red-600 text-sm">{formError}</p>
        )}

        <button
          type="submit"
          className="w-full bg-blue-600 hover:bg-blue-700 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
        >
          開始估算
        </button>
      </form>

      {submitted && (
        <div className="mb-8">
          <AllocationStrategy client={submitted} baseUrl="/api/allocation" />
        </div>
      )}

      <footer className="text-xs text-gray-400 border-t border-gray-100 pt-4 text-center">
        本工具提供配置參考，非正式保險建議，請諮詢合格業務員。
      </footer>
    </div>
  );
}
