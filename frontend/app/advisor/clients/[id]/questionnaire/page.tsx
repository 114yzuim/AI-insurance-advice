"use client";

import React, { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";

interface QForm {
  preferred_channels: string[];
  retire_income_sources: string[];
  retire_dreams: string[];
  retire_target_amount: number;
  retire_monthly_living: number;
  interested_topics: string[];
  monthly_investable_budget: number;
  risk_factors: string[];
  consent_advisory: boolean;
  has_existing_insurance: boolean;
  existing_policies_notes: string;
  health_status: string;
  has_family_disease: boolean;
  existing_medical_coverage: string;
  existing_ltc_coverage: string;
  has_existing_life_insurance: boolean;
  has_existing_medical_insurance: boolean;
  has_existing_accident_insurance: boolean;
  has_existing_annuity: boolean;
  has_existing_savings_insurance: boolean;
}

interface ClientProfile {
  name: string;
  age: number;
  family_status?: string;
  occupation?: string;
}

const DEFAULT_FORM: QForm = {
  preferred_channels: [],
  retire_income_sources: [],
  retire_dreams: [],
  retire_target_amount: 1000000,
  retire_monthly_living: 40000,
  interested_topics: [],
  monthly_investable_budget: 10000,
  risk_factors: [],
  consent_advisory: true,
  has_existing_insurance: false,
  existing_policies_notes: "",
  health_status: "良好",
  has_family_disease: false,
  existing_medical_coverage: "不清楚",
  existing_ltc_coverage: "不清楚",
  has_existing_life_insurance: false,
  has_existing_medical_insurance: false,
  has_existing_accident_insurance: false,
  has_existing_annuity: false,
  has_existing_savings_insurance: false,
};

const POLICY_SOURCES = ["紙本保單", "保單 PDF", "保險公司 App 截圖", "保單價值通知書", "繳費證明", "業務員既有資料", "診斷書／收據"];
const FAMILY_ROLES = ["家庭主要收入者", "共同收入者", "主要照顧者", "子女受扶養", "父母需照顧", "暫無扶養責任"];
const CHECK_GOALS = ["找保障缺口", "整理所有保單", "降低重複保費", "確認理賠可用性", "建立家庭保障總覽", "準備理賠服務"];
const REPORT_TOPICS = ["壽險保障", "醫療／實支實付", "意外保障", "失能／長照", "癌症險", "重大傷病", "保費占比", "除外責任與限制"];
const RISK_FACTORS = ["醫療自費風險", "癌症或重大傷病", "意外失能", "長照照護", "身故家庭責任", "保費過高", "重複保障", "理賠爭議"];
const MEDICAL_OPTS = ["不清楚", "沒有", "有住院日額", "有實支實付", "日額與實支都有"];
const LTC_OPTS = ["不清楚", "沒有", "每月 2 萬以下", "每月 3-4 萬", "每月 5 萬以上"];
const HEALTH_OPTS = ["良好", "有慢性病", "曾住院或手術", "正在追蹤治療", "不方便填寫"];

function Chip({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${
        selected
          ? "border-emerald-600 bg-emerald-600 text-white"
          : "border-gray-200 bg-white text-gray-700 hover:border-emerald-400"
      }`}
    >
      {children}
    </button>
  );
}

function QCard({ num, title, children }: { num: number; title: string; children: React.ReactNode }) {
  return (
    <section className="rounded-xl border border-gray-200 bg-white p-6">
      <div className="mb-4 flex items-baseline gap-3">
        <span className="font-mono text-xs text-gray-400">{String(num).padStart(2, "0")}</span>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      </div>
      {children}
    </section>
  );
}

function MoneyInput({ value, onChange, step = 1000 }: { value: number; onChange: (value: number) => void; step?: number }) {
  return (
    <div className="flex items-center gap-2">
      <span className="text-xs text-gray-400">NT$</span>
      <input
        type="number"
        min={0}
        step={step}
        value={value}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
        className="w-40 rounded-lg border border-gray-200 px-2.5 py-1.5 text-right text-sm focus:outline-none focus:ring-1 focus:ring-emerald-400"
      />
    </div>
  );
}

export default function QuestionnairePage() {
  const { id } = useParams<{ id: string }>();
  const [client, setClient] = useState<ClientProfile | null>(null);
  const [form, setForm] = useState<QForm>(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/advisor/clients/${id}`)
      .then((r) => r.json())
      .then((c) => setClient(c))
      .catch(() => {});
    fetch(`/api/advisor/questionnaires/${id}`)
      .then((r) => r.json())
      .then((data) => {
        if (data) setForm({ ...DEFAULT_FORM, ...data });
      })
      .catch(() => {});
  }, [id]);

  const toggle = (field: keyof QForm, val: string) => {
    setForm((f) => {
      const arr = (f[field] as string[]) ?? [];
      return { ...f, [field]: arr.includes(val) ? arr.filter((v) => v !== val) : [...arr, val] };
    });
  };
  const set = <K extends keyof QForm>(k: K, v: QForm[K]) => setForm((f) => ({ ...f, [k]: v }));

  const handleSave = async () => {
    setSaving(true);
    setSaved(false);
    setError(null);
    try {
      const res = await fetch(`/api/advisor/questionnaires/${id}`, {
        method: "PUT",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify(form),
      });
      const data = await res.json();
      if (!res.ok) {
        setError(data.detail || "儲存失敗");
        return;
      }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch {
      setError("儲存失敗");
    } finally {
      setSaving(false);
    }
  };

  const policyTypes: Array<[keyof QForm, string]> = [
    ["has_existing_life_insurance", "壽險"],
    ["has_existing_medical_insurance", "醫療／實支"],
    ["has_existing_accident_insurance", "意外險"],
    ["has_existing_annuity", "年金險"],
    ["has_existing_savings_insurance", "儲蓄險"],
  ];

  return (
    <div className="mx-auto max-w-3xl px-4 py-8">
      <div className="mb-6">
        <Link href={`/advisor/clients/${id}`} className="text-sm text-gray-400 hover:text-gray-600">
          ← {client?.name || "客戶"}
        </Link>
        <h1 className="mt-2 text-2xl font-bold text-gray-900">保單健診資料補充表</h1>
        <p className="mt-2 text-sm leading-6 text-gray-500">
          這份表單用來補足保單健診報告需要的家庭責任、既有保單狀態與理賠服務需求。年齡改用客戶資料中的精確數字。
        </p>
      </div>

      <section className="mb-4 rounded-xl border border-emerald-100 bg-emerald-50 p-4">
        <div className="grid gap-3 text-sm sm:grid-cols-2">
          <Info label="客戶" value={client?.name || "-"} />
          <Info label="精確年齡" value={client?.age ? `${client.age} 歲` : "尚未填寫"} />
          <Info label="家庭狀況" value={client?.family_status || "-"} />
          <Info label="職業" value={client?.occupation || "-"} />
        </div>
        <Link href={`/advisor/clients/${id}/edit`} className="mt-3 inline-block text-xs font-medium text-emerald-700 hover:text-emerald-900">
          修改客戶基本資料
        </Link>
      </section>

      <div className="space-y-4">
        <QCard num={1} title="目前已取得哪些保單或理賠資料？">
          <div className="flex flex-wrap gap-2">
            {POLICY_SOURCES.map((o) => (
              <Chip key={o} selected={form.preferred_channels.includes(o)} onClick={() => toggle("preferred_channels", o)}>
                {o}
              </Chip>
            ))}
          </div>
        </QCard>

        <QCard num={2} title="這位客戶在家庭中的責任角色">
          <div className="flex flex-wrap gap-2">
            {FAMILY_ROLES.map((o) => (
              <Chip key={o} selected={form.retire_income_sources.includes(o)} onClick={() => toggle("retire_income_sources", o)}>
                {o}
              </Chip>
            ))}
          </div>
        </QCard>

        <QCard num={3} title="本次保單健診目的">
          <div className="flex flex-wrap gap-2">
            {CHECK_GOALS.map((o) => (
              <Chip key={o} selected={form.retire_dreams.includes(o)} onClick={() => toggle("retire_dreams", o)}>
                {o}
              </Chip>
            ))}
          </div>
        </QCard>

        <QCard num={4} title="家庭責任或主要負債總額">
          <p className="mb-3 text-xs leading-5 text-gray-400">可包含房貸、扶養責任、子女教育金與緊急預備金。沒有明確數字可先填粗估。</p>
          <MoneyInput value={form.retire_target_amount} step={100000} onChange={(value) => set("retire_target_amount", value)} />
        </QCard>

        <QCard num={5} title="家庭每月必要支出">
          <MoneyInput value={form.retire_monthly_living} onChange={(value) => set("retire_monthly_living", value)} />
        </QCard>

        <QCard num={6} title="健診報告需要特別呈現的項目">
          <div className="flex flex-wrap gap-2">
            {REPORT_TOPICS.map((o) => (
              <Chip key={o} selected={form.interested_topics.includes(o)} onClick={() => toggle("interested_topics", o)}>
                {o}
              </Chip>
            ))}
          </div>
        </QCard>

        <QCard num={7} title="每月可接受保費預算">
          <MoneyInput value={form.monthly_investable_budget} onChange={(value) => set("monthly_investable_budget", value)} />
        </QCard>

        <QCard num={8} title="客戶最擔心的風險">
          <div className="flex flex-wrap gap-2">
            {RISK_FACTORS.map((o) => (
              <Chip key={o} selected={form.risk_factors.includes(o)} onClick={() => toggle("risk_factors", o)}>
                {o}
              </Chip>
            ))}
          </div>
        </QCard>

        <QCard num={9} title="健康狀況與家族病史">
          <div className="mb-4">
            <div className="mb-2 text-xs text-gray-400">目前健康狀況</div>
            <div className="flex flex-wrap gap-2">
              {HEALTH_OPTS.map((o) => (
                <Chip key={o} selected={form.health_status === o} onClick={() => set("health_status", o)}>
                  {o}
                </Chip>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-2 text-xs text-gray-400">家族是否有重大疾病史？</div>
            <div className="flex gap-2">
              <Chip selected={Boolean(form.has_family_disease)} onClick={() => set("has_family_disease", true)}>有</Chip>
              <Chip selected={!form.has_family_disease} onClick={() => set("has_family_disease", false)}>沒有或不清楚</Chip>
            </div>
          </div>
        </QCard>

        <QCard num={10} title="既有醫療與長照保障概況">
          <div className="mb-4">
            <div className="mb-2 text-xs text-gray-400">醫療保障</div>
            <div className="flex flex-wrap gap-2">
              {MEDICAL_OPTS.map((o) => (
                <Chip key={o} selected={form.existing_medical_coverage === o} onClick={() => set("existing_medical_coverage", o)}>
                  {o}
                </Chip>
              ))}
            </div>
          </div>
          <div>
            <div className="mb-2 text-xs text-gray-400">失能／長照保障</div>
            <div className="flex flex-wrap gap-2">
              {LTC_OPTS.map((o) => (
                <Chip key={o} selected={form.existing_ltc_coverage === o} onClick={() => set("existing_ltc_coverage", o)}>
                  {o}
                </Chip>
              ))}
            </div>
          </div>
        </QCard>

        <QCard num={11} title="既有保單類型與補充說明">
          <div className="mb-4">
            <div className="mb-2 text-xs text-gray-400">是否已有保單？</div>
            <div className="flex gap-2">
              <Chip selected={Boolean(form.has_existing_insurance)} onClick={() => set("has_existing_insurance", true)}>有</Chip>
              <Chip selected={!form.has_existing_insurance} onClick={() => set("has_existing_insurance", false)}>沒有或不確定</Chip>
            </div>
          </div>
          <div className="mb-4">
            <div className="mb-2 text-xs text-gray-400">已知保單類型</div>
            <div className="flex flex-wrap gap-2">
              {policyTypes.map(([key, label]) => (
                <Chip key={key} selected={Boolean(form[key])} onClick={() => set(key, !form[key] as never)}>
                  {label}
                </Chip>
              ))}
            </div>
          </div>
          <textarea
            rows={4}
            value={form.existing_policies_notes}
            onChange={(e) => set("existing_policies_notes", e.target.value)}
            placeholder="例如：國泰 2 張、富邦 1 張；保費偏高；家人最近住院想確認哪些保單可理賠。"
            className="w-full resize-none rounded-lg border border-gray-200 px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-400"
          />
          <div className="mt-4 border-t border-gray-100 pt-4">
            <div className="mb-2 text-xs text-gray-400">是否同意顧問依上述資料提供健診與後續追蹤？</div>
            <div className="flex gap-2">
              <Chip selected={Boolean(form.consent_advisory)} onClick={() => set("consent_advisory", true)}>同意</Chip>
              <Chip selected={!form.consent_advisory} onClick={() => set("consent_advisory", false)}>暫不同意</Chip>
            </div>
          </div>
        </QCard>

        {error && <p className="text-sm text-red-500">{error}</p>}

        <div className="flex gap-3">
          <Link href={`/advisor/clients/${id}`} className="flex-1 rounded-lg border border-gray-300 py-2.5 text-center text-sm text-gray-600 transition-colors hover:bg-gray-50">
            返回
          </Link>
          <button
            onClick={handleSave}
            disabled={saving}
            className="flex-1 rounded-lg bg-emerald-600 py-2.5 text-sm font-medium text-white transition-colors hover:bg-emerald-700 disabled:opacity-50"
          >
            {saving ? "儲存中..." : saved ? "已儲存" : "儲存健診資料"}
          </button>
        </div>
      </div>
    </div>
  );
}

function Info({ label, value }: { label: string; value: string }) {
  return (
    <div>
      <p className="text-xs text-emerald-700">{label}</p>
      <p className="mt-1 font-medium text-gray-900">{value}</p>
    </div>
  );
}
