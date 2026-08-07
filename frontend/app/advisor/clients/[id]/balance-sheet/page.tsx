"use client";
import React, { useEffect, useMemo, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

// ─── types ───────────────────────────────────────────────────────────────────

interface Assets {
  cash: { demand_deposit: number; reserve: number; time_deposit: number; foreign_currency: number };
  investment: { stocks_funds: number; endowment_twd: number; other_investment: number };
  real_estate: { house: number; land: number };
  movable: { vehicle: number };
  income: { salary: number; side_income: number; other_income: number };
}
interface Debt { balance: number; monthly_payment: number }
interface Liabilities {
  fixed: { mortgage: Debt; car_loan: Debt; other_loan: Debt };
  general: { living: number; rent: number; phone: number; other: number };
}

// ─── initial state ────────────────────────────────────────────────────────────

const ED: Debt = { balance: 0, monthly_payment: 0 };
const EMPTY_ASSETS: Assets = {
  cash: { demand_deposit: 0, reserve: 0, time_deposit: 0, foreign_currency: 0 },
  investment: { stocks_funds: 0, endowment_twd: 0, other_investment: 0 },
  real_estate: { house: 0, land: 0 },
  movable: { vehicle: 0 },
  income: { salary: 0, side_income: 0, other_income: 0 },
};
const EMPTY_LIABILITIES: Liabilities = {
  fixed: { mortgage: { ...ED }, car_loan: { ...ED }, other_loan: { ...ED } },
  general: { living: 0, rent: 0, phone: 0, other: 0 },
};

// ─── helpers ──────────────────────────────────────────────────────────────────

function sumObj(obj: Record<string, number>): number {
  return Object.values(obj).reduce((a, v) => a + (v || 0), 0);
}
function tw(n: number): string {
  if (n === 0) return "0";
  return n.toLocaleString("zh-TW");
}

// ─── sub-components ───────────────────────────────────────────────────────────

function NumInput({ value, onChange }: { value: number; onChange: (v: number) => void }) {
  return (
    <input
      type="number" min={0} placeholder="0"
      value={value || ""}
      onChange={(e) => onChange(parseFloat(e.target.value) || 0)}
      className="w-full border border-gray-200 rounded-md px-2.5 py-1.5 text-sm text-right tabular-nums focus:outline-none focus:ring-1 focus:ring-blue-400 bg-white"
    />
  );
}

function Row({ label, value, onChange }: { label: string; value: number; onChange: (v: number) => void }) {
  return (
    <div className="flex items-center gap-2">
      <span className="flex-1 text-xs text-gray-500 truncate">{label}</span>
      <div className="w-36 shrink-0">
        <NumInput value={value} onChange={onChange} />
      </div>
    </div>
  );
}

function Subtotal({ label, value, unit = "元" }: { label?: string; value: number; unit?: string }) {
  return (
    <div className="flex items-center justify-between mt-2 pt-2 border-t border-dashed border-gray-200">
      <span className="text-xs text-gray-400">{label ?? "小計"}</span>
      <span className="text-xs font-semibold text-gray-700 tabular-nums">{tw(value)} {unit}</span>
    </div>
  );
}

function Section({ title, children }: { title: string; children: React.ReactNode }) {
  return (
    <div className="mb-5">
      <div className="text-xs font-semibold text-gray-500 uppercase tracking-wide mb-2">{title}</div>
      <div className="space-y-2">{children}</div>
    </div>
  );
}

function SummaryCard({
  label, value, color, unit = "元",
}: {
  label: string; value: number; color: "green" | "red" | "dynamic"; unit?: string;
}) {
  const cls =
    color === "green" ? "bg-green-50 border-green-200 text-green-700"
    : color === "red" ? "bg-red-50 border-red-200 text-red-700"
    : value >= 0 ? "bg-green-50 border-green-200 text-green-700"
    : "bg-red-50 border-red-200 text-red-600";

  return (
    <div className={`rounded-xl border px-4 py-3 ${cls}`}>
      <div className="text-xs opacity-70 mb-1">{label}</div>
      <div className="text-lg font-bold tabular-nums">
        {value >= 0 ? "" : "−"}{tw(Math.abs(value))}
        <span className="text-xs font-normal ml-1">{unit}</span>
      </div>
    </div>
  );
}

// ─── page ─────────────────────────────────────────────────────────────────────

export default function BalanceSheetPage() {
  const { id } = useParams<{ id: string }>();
  const [clientName, setClientName] = useState("");
  const [assets, setAssets] = useState<Assets>(EMPTY_ASSETS);
  const [liabilities, setLiabilities] = useState<Liabilities>(EMPTY_LIABILITIES);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/advisor/clients/${id}`).then((r) => r.json()).then((c) => setClientName(c.name)).catch(() => {});
    fetch(`/api/advisor/clients/${id}/balance-sheet`).then((r) => r.json()).then((data) => {
      if (!data) return;
      if (data.assets) setAssets({ ...EMPTY_ASSETS, ...data.assets });
      if (data.liabilities) setLiabilities({ ...EMPTY_LIABILITIES, ...data.liabilities });
    }).catch(() => {});
  }, [id]);

  // ── asset setters ──
  const setA = <S extends keyof Assets, F extends keyof Assets[S]>(s: S, f: F, v: number) =>
    setAssets((a) => ({ ...a, [s]: { ...a[s], [f]: v } }));
  const setDebt = (k: keyof Liabilities["fixed"], f: keyof Debt, v: number) =>
    setLiabilities((l) => ({ ...l, fixed: { ...l.fixed, [k]: { ...l.fixed[k], [f]: v } } }));
  const setGen = (k: keyof Liabilities["general"], v: number) =>
    setLiabilities((l) => ({ ...l, general: { ...l.general, [k]: v } }));

  // ── real-time computed ──
  const computed = useMemo(() => {
    const cashTotal = sumObj(assets.cash);
    const investTotal = sumObj(assets.investment);
    const realEstateTotal = sumObj(assets.real_estate);
    const movableTotal = sumObj(assets.movable);
    const incomeTotal = sumObj(assets.income);
    const totalAssets = cashTotal + investTotal + realEstateTotal + movableTotal;

    const fixedBalance = Object.values(liabilities.fixed).reduce((a, d) => a + (d.balance || 0), 0);
    const fixedMonthly = Object.values(liabilities.fixed).reduce((a, d) => a + (d.monthly_payment || 0), 0);
    const generalTotal = sumObj(liabilities.general);

    const totalLiabilities = fixedBalance;
    const monthlyExpense = fixedMonthly + generalTotal;
    const netWorth = totalAssets - totalLiabilities;
    const monthlyBalance = incomeTotal - monthlyExpense;

    return {
      cashTotal, investTotal, realEstateTotal, movableTotal, incomeTotal,
      fixedBalance, fixedMonthly, generalTotal,
      totalAssets, totalLiabilities, monthlyExpense, netWorth, monthlyBalance,
    };
  }, [assets, liabilities]);

  const handleSave = async () => {
    setSaving(true); setSaved(false); setError(null);
    try {
      const res = await fetch(`/api/advisor/clients/${id}/balance-sheet`, {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ assets, liabilities }),
      });
      if (!res.ok) { const d = await res.json(); setError(d.detail || "儲存失敗"); return; }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch { setError("儲存失敗"); } finally { setSaving(false); }
  };

  return (
    <div className="max-w-5xl mx-auto px-4 py-8">
      {/* breadcrumb */}
      <div className="mb-6">
        <Link href={`/advisor/clients/${id}`} className="text-sm text-gray-400 hover:text-gray-600">
          ← {clientName || "客戶"}
        </Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">資產負債表</h1>
      </div>

      {/* ── real-time summary ────────────────────────────────────────────── */}
      <div className="mb-6 space-y-2">
        <div className="grid grid-cols-3 gap-3">
          <SummaryCard label="總資產" value={computed.totalAssets} color="green" />
          <SummaryCard label="總負債（餘額）" value={computed.totalLiabilities} color="red" />
          <SummaryCard label="淨資產" value={computed.netWorth} color="dynamic" />
        </div>
        <div className="grid grid-cols-3 gap-3">
          <SummaryCard label="月收入" value={computed.incomeTotal} color="green" unit="元/月" />
          <SummaryCard label="月支出" value={computed.monthlyExpense} color="red" unit="元/月" />
          <SummaryCard label="月結餘" value={computed.monthlyBalance} color="dynamic" unit="元/月" />
        </div>
      </div>

      {/* ── two-column form ──────────────────────────────────────────────── */}
      <div className="grid grid-cols-1 lg:grid-cols-2 gap-4">

        {/* ── LEFT: Assets ── */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="font-semibold text-gray-800 mb-5 flex items-center gap-2">
            <span className="w-2 h-5 bg-green-500 rounded-full inline-block" />
            資產
          </h2>

          <Section title="現金與存款">
            <Row label="現金 / 活存" value={assets.cash.demand_deposit} onChange={(v) => setA("cash", "demand_deposit", v)} />
            <Row label="預備金" value={assets.cash.reserve} onChange={(v) => setA("cash", "reserve", v)} />
            <Row label="定存" value={assets.cash.time_deposit} onChange={(v) => setA("cash", "time_deposit", v)} />
            <Row label="外幣" value={assets.cash.foreign_currency} onChange={(v) => setA("cash", "foreign_currency", v)} />
            <Subtotal value={computed.cashTotal} />
          </Section>

          <Section title="儲蓄與投資">
            <Row label="股票 / 基金" value={assets.investment.stocks_funds} onChange={(v) => setA("investment", "stocks_funds", v)} />
            <Row label="儲蓄險" value={assets.investment.endowment_twd} onChange={(v) => setA("investment", "endowment_twd", v)} />
            <Row label="其他投資" value={assets.investment.other_investment} onChange={(v) => setA("investment", "other_investment", v)} />
            <Subtotal value={computed.investTotal} />
          </Section>

          <Section title="不動產（市值）">
            <Row label="房屋" value={assets.real_estate.house} onChange={(v) => setA("real_estate", "house", v)} />
            <Row label="土地" value={assets.real_estate.land} onChange={(v) => setA("real_estate", "land", v)} />
            <Subtotal value={computed.realEstateTotal} />
          </Section>

          <Section title="動產（殘值）">
            <Row label="汽車" value={assets.movable.vehicle} onChange={(v) => setA("movable", "vehicle", v)} />
            <Subtotal value={computed.movableTotal} />
          </Section>

          <Section title="收入現況（月）">
            <Row label="薪資（月）" value={assets.income.salary} onChange={(v) => setA("income", "salary", v)} />
            <Row label="兼職 / 現金收入（月）" value={assets.income.side_income} onChange={(v) => setA("income", "side_income", v)} />
            <Row label="其他收入（月）" value={assets.income.other_income} onChange={(v) => setA("income", "other_income", v)} />
            <Subtotal label="月收入小計" value={computed.incomeTotal} unit="元/月" />
          </Section>
        </div>

        {/* ── RIGHT: Liabilities ── */}
        <div className="bg-white border border-gray-200 rounded-xl p-5">
          <h2 className="font-semibold text-gray-800 mb-5 flex items-center gap-2">
            <span className="w-2 h-5 bg-red-400 rounded-full inline-block" />
            負債
          </h2>

          <Section title="固定負債">
            {(
              [
                ["mortgage", "房貸"],
                ["car_loan", "車貸"],
                ["other_loan", "其他貸款"],
              ] as const
            ).map(([key, label]) => (
              <div key={key} className="mb-3">
                <div className="text-xs text-gray-500 mb-1 font-medium">{label}</div>
                <div className="space-y-1.5 pl-2">
                  <Row label="餘額" value={liabilities.fixed[key].balance} onChange={(v) => setDebt(key, "balance", v)} />
                  <Row label="月還款" value={liabilities.fixed[key].monthly_payment} onChange={(v) => setDebt(key, "monthly_payment", v)} />
                </div>
              </div>
            ))}
            <div className="flex items-center justify-between mt-2 pt-2 border-t border-dashed border-gray-200 gap-4">
              <span className="text-xs text-gray-400">小計</span>
              <div className="flex gap-4 text-xs font-semibold text-gray-700 tabular-nums">
                <span>餘額：{tw(computed.fixedBalance)} 元</span>
                <span>月還款：{tw(computed.fixedMonthly)} 元</span>
              </div>
            </div>
          </Section>

          <Section title="每月支出">
            <Row label="生活費（月）" value={liabilities.general.living} onChange={(v) => setGen("living", v)} />
            <Row label="房租（月）" value={liabilities.general.rent} onChange={(v) => setGen("rent", v)} />
            <Row label="電話費（月）" value={liabilities.general.phone} onChange={(v) => setGen("phone", v)} />
            <Row label="其他（月）" value={liabilities.general.other} onChange={(v) => setGen("other", v)} />
            <Subtotal label="月支出小計" value={computed.generalTotal} unit="元/月" />
          </Section>
        </div>
      </div>

      {/* ── actions ── */}
      {error && <p className="text-red-500 text-sm mt-4">{error}</p>}
      <div className="flex gap-3 mt-4">
        <Link
          href={`/advisor/clients/${id}`}
          className="flex-1 py-2.5 rounded-lg border border-gray-300 text-sm text-center text-gray-600 hover:bg-gray-50 transition-colors"
        >
          返回
        </Link>
        <button
          onClick={handleSave}
          disabled={saving}
          className="flex-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition-colors"
        >
          {saving ? "儲存中…" : saved ? "已儲存 ✓" : "儲存資產負債表"}
        </button>
      </div>
    </div>
  );
}
