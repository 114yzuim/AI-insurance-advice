"use client";
import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { AllocationStrategy } from "@/components/allocation/AllocationStrategy";
import AccumulationChart from "@/components/allocation/AccumulationChart";
import { toAccPoints } from "@/components/allocation/chart-adapters";
import type { AccPoint } from "@/components/allocation/chart-types";
import "@/components/allocation/styles.css";
import type { ClientInputs, RiskTolerance } from "@/components/allocation/types";
import type { ViewModel } from "@/components/allocation/AllocationStrategy";

interface AdvisorClient {
  id: number;
  name: string;
  age: number;
  target_retire_age: number | null;
  life_expectancy: number | null;
  monthly_investable: number | null;
  current_assets: number | null;
  target_retire_monthly_expense: number | null;
  risk_tolerance: string | null;
}

interface Questionnaire {
  has_existing_medical_insurance: number;
  has_existing_life_insurance: number;
}

const CATEGORY_RATES = { A: 0.06, B: 0.022, C: 0.0 };

function mapRisk(raw: string | null | undefined): RiskTolerance {
  if (raw === "low") return "low";
  if (raw === "high") return "high";
  return "mid";
}

function fmt(n: number | null | undefined, unit = "元"): string {
  if (n == null || n === 0) return "—";
  return `${n.toLocaleString("zh-TW")} ${unit}`;
}

export default function ClientRetirementPage() {
  const { id } = useParams<{ id: string }>();
  const [client, setClient] = useState<AdvisorClient | null>(null);
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const [chartData, setChartData] = useState<AccPoint[] | null>(null);
  const [chartLoading, setChartLoading] = useState(false);
  const [chartError, setChartError] = useState<string | null>(null);
  const [chartRetireAge, setChartRetireAge] = useState(65);
  const [achievementRatio, setAchievementRatio] = useState<number | null>(null);
  const [affordableMonthly, setAffordableMonthly] = useState<number | null>(null);

  useEffect(() => {
    Promise.all([
      fetch(`/api/advisor/clients/${id}`).then((r) => r.json()),
      fetch(`/api/advisor/questionnaires/${id}`).then((r) => r.json()).catch(() => null),
    ])
      .then(([c, q]) => {
        setClient(c);
        setQuestionnaire(q);
      })
      .catch(() => setError("載入失敗"))
      .finally(() => setLoading(false));
  }, [id]);

  // Map client data → AllocationStrategy ClientInputs
  const submitted = useMemo<ClientInputs | null>(() => {
    if (!client) return null;
    return {
      age: client.age,
      retireAge: client.target_retire_age ?? 65,
      monthlyInvestable: client.monthly_investable ?? 0,
      dependents: 0,
      riskTolerance: mapRisk(client.risk_tolerance),
      hasMedicalCoverage: Boolean(questionnaire?.has_existing_medical_insurance),
      hasLifeCoverage: Boolean(questionnaire?.has_existing_life_insurance),
    };
  }, [client, questionnaire]);

  async function handleAllocationNext(view: ViewModel) {
    if (!client) return;
    setChartLoading(true);
    setChartError(null);
    setChartData(null);

    const { a, b, c } = view.allocation;
    const blendedRate =
      (a * CATEGORY_RATES.A + b * CATEGORY_RATES.B + c * CATEGORY_RATES.C) / 100;

    try {
      const res = await fetch("/api/simulator/forward", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({
          current_age: client.age,
          retire_age: client.target_retire_age ?? 65,
          life_expectancy: client.life_expectancy ?? 85,
          current_assets_twd: client.current_assets ?? 0,
          monthly_saving_twd: client.monthly_investable ?? 0,
          target_monthly_expense_twd: client.target_retire_monthly_expense ?? 40000,
          annual_rate: blendedRate,
        }),
      });
      const data = await res.json();
      if (!res.ok) {
        setChartError(data.detail || "試算失敗");
        return;
      }
      setChartData(toAccPoints(data.result.yearly_assets));
      setChartRetireAge(client.target_retire_age ?? 65);
      setAchievementRatio(data.result.achievement_ratio);
      setAffordableMonthly(data.result.affordable_monthly_withdrawal_twd);
    } catch {
      setChartError("試算失敗，請稍後再試。");
    } finally {
      setChartLoading(false);
    }
  }

  if (loading) return <div className="text-center py-16 text-gray-400 text-sm">載入中…</div>;
  if (error || !client || !submitted) return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <p className="text-red-500 text-sm">{error ?? "找不到客戶資料"}</p>
      <Link href="/advisor" className="text-blue-500 text-sm">← 返回</Link>
    </div>
  );

  return (
    <div className="max-w-3xl mx-auto px-4 py-8">
      <div className="mb-6">
        <Link href={`/advisor/clients/${id}`} className="text-sm text-gray-400 hover:text-gray-600">
          ← {client.name}
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">退休規劃試算</h1>
      </div>

      {/* Client params summary */}
      <div className="bg-blue-50 border border-blue-100 rounded-xl px-5 py-4 mb-6 text-sm">
        <div className="text-xs font-semibold text-blue-600 uppercase tracking-wide mb-2">套用客戶資料</div>
        <div className="grid grid-cols-3 gap-3 text-gray-700">
          <div><span className="text-gray-400">年齡 / 退休</span><div className="font-medium">{client.age} → {client.target_retire_age ?? 65} 歲</div></div>
          <div><span className="text-gray-400">每月可投入</span><div className="font-medium">{fmt(client.monthly_investable)}</div></div>
          <div><span className="text-gray-400">現有資產</span><div className="font-medium">{fmt(client.current_assets)}</div></div>
          <div><span className="text-gray-400">退休月支出目標</span><div className="font-medium">{fmt(client.target_retire_monthly_expense)}</div></div>
          <div><span className="text-gray-400">平均餘命</span><div className="font-medium">{client.life_expectancy ?? 85} 歲</div></div>
          <div><span className="text-gray-400">風險偏好</span><div className="font-medium">{{ low: "低", mid: "中", high: "高" }[mapRisk(client.risk_tolerance)]}</div></div>
        </div>
        <p className="text-xs text-gray-400 mt-3">
          如需修改參數，請返回客戶資料頁更新後重新試算。
        </p>
      </div>

      {/* Allocation strategy */}
      <div className="mb-6">
        <AllocationStrategy
          client={submitted}
          baseUrl="/api/allocation"
          onNext={handleAllocationNext}
          nextLabel="計算退休曲線 →"
        />
      </div>

      {/* Chart section */}
      {(chartLoading || chartData || chartError) && (
        <div className="bg-white border border-gray-200 rounded-xl p-6">
          <h2 className="text-lg font-semibold text-gray-800 mb-1">退休資產規劃曲線</h2>
          <p className="text-xs text-gray-400 mb-4">
            依 A/B/C 配置加權報酬率計算，非保險公司正式建議書。
          </p>

          {chartLoading && (
            <div className="flex items-center justify-center py-12 gap-3 text-gray-400 text-sm">
              <span className="w-5 h-5 border-2 border-blue-400 border-t-transparent rounded-full animate-spin" />
              試算中…
            </div>
          )}

          {chartError && <p className="text-red-500 text-sm py-6 text-center">{chartError}</p>}

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
                本試算為概念性數字，非正式建議書。實際結果受市場、通膨、健康因素影響。
              </p>
            </>
          )}
        </div>
      )}
    </div>
  );
}
