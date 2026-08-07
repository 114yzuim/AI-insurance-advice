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

const DEFAULT_FORM: QForm = {
  preferred_channels: [], retire_income_sources: [], retire_dreams: [],
  retire_target_amount: 1000, retire_monthly_living: 40000,
  interested_topics: [], monthly_investable_budget: 10000,
  risk_factors: [], consent_advisory: true,
  has_existing_insurance: false, existing_policies_notes: "",
  health_status: "良好", has_family_disease: false,
  existing_medical_coverage: "不清楚", existing_ltc_coverage: "不清楚",
  has_existing_life_insurance: false, has_existing_medical_insurance: false,
  has_existing_accident_insurance: false, has_existing_annuity: false,
  has_existing_savings_insurance: false,
};

function Chip({ selected, onClick, children }: { selected: boolean; onClick: () => void; children: React.ReactNode }) {
  return (
    <button type="button" onClick={onClick}
      className={`rounded-lg border px-3 py-1.5 text-sm transition-colors ${selected ? "border-emerald-600 bg-emerald-600 text-white" : "border-gray-200 bg-white text-gray-700 hover:border-emerald-400"}`}>
      {children}
    </button>
  );
}

function QCard({ num, title, children }: { num: number; title: string; children: React.ReactNode }) {
  return (
    <section className="bg-white rounded-xl border border-gray-200 p-6">
      <div className="flex items-baseline gap-3 mb-4">
        <span className="font-mono text-xs text-gray-400">{String(num).padStart(2, "0")}</span>
        <h3 className="text-sm font-semibold text-gray-900">{title}</h3>
      </div>
      {children}
    </section>
  );
}

const CHANNELS = ["銀行存款", "外幣存款", "標會", "保險理財", "股票", "基金", "其他"];
const INCOME_SOURCES = ["政府的老人年金", "社會團體的支援", "子女的奉養", "自己規劃的退休金"];
const DREAMS = ["環遊世界", "學習新知", "公益活動", "發展事業第二春", "含飴弄孫", "協助子女成家立業", "其他"];
const TOPICS = ["個人儲蓄投資理財", "節稅資訊", "退休理財規劃", "房貸理財計劃"];
const RISK_FACTORS = ["壽命延長", "失業率高", "稅賦負擔", "生活費用高", "醫療費用增加", "少子化", "離婚率高", "存款利率低", "投資風險高", "社會福利不足"];
const RETIRE_AMOUNTS = [500, 700, 1000, 1500, 3000, 4200];
const MONTHLY_LIVING = [20000, 30000, 40000, 50000, 80000, 120000];
const MONTHLY_BUDGETS = [5000, 10000, 20000, 30000, 50000];
const MEDICAL_OPTS = ["無", "不清楚", "5 萬以內", "10 萬左右", "20 萬以上"];
const LTC_OPTS = ["無", "不清楚", "2 萬以內", "3~4 萬", "5 萬以上"];

export default function QuestionnairePage() {
  const { id } = useParams<{ id: string }>();
  const [clientName, setClientName] = useState("");
  const [form, setForm] = useState<QForm>(DEFAULT_FORM);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);

  useEffect(() => {
    fetch(`/api/advisor/clients/${id}`).then((r) => r.json()).then((c) => setClientName(c.name)).catch(() => {});
    fetch(`/api/advisor/questionnaires/${id}`).then((r) => r.json()).then((data) => {
      if (data) setForm({ ...DEFAULT_FORM, ...data });
    }).catch(() => {});
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
      if (!res.ok) { setError(data.detail || "儲存失敗"); return; }
      setSaved(true);
      setTimeout(() => setSaved(false), 2500);
    } catch { setError("儲存失敗"); } finally { setSaving(false); }
  };

  return (
    <div className="max-w-2xl mx-auto px-4 py-8">
      <div className="mb-6">
        <Link href={`/advisor/clients/${id}`} className="text-sm text-gray-400 hover:text-gray-600">← {clientName || "客戶"}</Link>
        <h1 className="text-2xl font-bold text-gray-900 mt-2">退休規劃問卷</h1>
      </div>

      <div className="space-y-4">
        <QCard num={1} title="喜歡哪些投資理財管道？（可複選）">
          <div className="flex flex-wrap gap-2">{CHANNELS.map((o) => <Chip key={o} selected={form.preferred_channels.includes(o)} onClick={() => toggle("preferred_channels", o)}>{o}</Chip>)}</div>
        </QCard>

        <QCard num={2} title="最有保障的退休收入來源？（可複選）">
          <div className="flex flex-wrap gap-2">{INCOME_SOURCES.map((o) => <Chip key={o} selected={form.retire_income_sources.includes(o)} onClick={() => toggle("retire_income_sources", o)}>{o}</Chip>)}</div>
        </QCard>

        <QCard num={3} title="退休後想做哪些事？（可複選）">
          <div className="flex flex-wrap gap-2">{DREAMS.map((o) => <Chip key={o} selected={form.retire_dreams.includes(o)} onClick={() => toggle("retire_dreams", o)}>{o}</Chip>)}</div>
        </QCard>

        <QCard num={4} title="退休需要準備多少退休金？">
          <div className="flex flex-wrap gap-2 mb-3">{RETIRE_AMOUNTS.map((a) => <Chip key={a} selected={form.retire_target_amount === a} onClick={() => set("retire_target_amount", a)}>{a} 萬</Chip>)}</div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">自訂</span>
            <input type="number" min={0} value={form.retire_target_amount}
              onChange={(e) => set("retire_target_amount", Number(e.target.value) || 0)}
              className="w-28 border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm text-right focus:outline-none focus:ring-1 focus:ring-emerald-400" />
            <span className="text-xs text-gray-400">萬元</span>
          </div>
        </QCard>

        <QCard num={5} title="退休後每月生活費目標？">
          <div className="flex flex-wrap gap-2 mb-3">{MONTHLY_LIVING.map((a) => <Chip key={a} selected={form.retire_monthly_living === a} onClick={() => set("retire_monthly_living", a)}>{(a / 10000).toFixed(0)} 萬元</Chip>)}</div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">自訂</span>
            <input type="number" min={0} step={1000} value={form.retire_monthly_living}
              onChange={(e) => set("retire_monthly_living", Number(e.target.value) || 0)}
              className="w-32 border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm text-right focus:outline-none focus:ring-1 focus:ring-emerald-400" />
            <span className="text-xs text-gray-400">元</span>
          </div>
        </QCard>

        <QCard num={6} title="希望了解的理財資訊（可複選）">
          <div className="flex flex-wrap gap-2">{TOPICS.map((o) => <Chip key={o} selected={form.interested_topics.includes(o)} onClick={() => toggle("interested_topics", o)}>{o}</Chip>)}</div>
        </QCard>

        <QCard num={7} title="每月可投入儲蓄或投資？">
          <div className="flex flex-wrap gap-2 mb-3">
            {MONTHLY_BUDGETS.map((a) => <Chip key={a} selected={form.monthly_investable_budget === a} onClick={() => set("monthly_investable_budget", a)}>{a >= 10000 ? `${a / 10000} 萬元` : `${a.toLocaleString()} 元`}</Chip>)}
            <Chip selected={form.monthly_investable_budget > 50000} onClick={() => set("monthly_investable_budget", 60000)}>5 萬以上</Chip>
          </div>
          <div className="flex items-center gap-2">
            <span className="text-xs text-gray-400">自訂</span>
            <input type="number" min={0} step={1000} value={form.monthly_investable_budget}
              onChange={(e) => set("monthly_investable_budget", Number(e.target.value) || 0)}
              className="w-32 border border-gray-200 rounded-lg px-2.5 py-1.5 text-sm text-right focus:outline-none focus:ring-1 focus:ring-emerald-400" />
            <span className="text-xs text-gray-400">元/月</span>
          </div>
        </QCard>

        <QCard num={8} title="影響您準備退休金的因素？（可複選）">
          <div className="flex flex-wrap gap-2">{RISK_FACTORS.map((o) => <Chip key={o} selected={form.risk_factors.includes(o)} onClick={() => toggle("risk_factors", o)}>{o}</Chip>)}</div>
        </QCard>

        <QCard num={9} title="健康狀況與家族病史">
          <div className="mb-4">
            <div className="text-xs text-gray-400 mb-2">健康狀況</div>
            <div className="flex flex-wrap gap-2">
              {["極佳", "良好", "有定期服藥", "有重大病史", "曾有拒保紀錄"].map((o) => <Chip key={o} selected={form.health_status === o} onClick={() => set("health_status", o)}>{o}</Chip>)}
            </div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-2">直系親屬是否有重大遺傳疾病？</div>
            <div className="flex gap-2">
              <Chip selected={form.has_family_disease} onClick={() => set("has_family_disease", true)}>是</Chip>
              <Chip selected={!form.has_family_disease} onClick={() => set("has_family_disease", false)}>否</Chip>
            </div>
          </div>
        </QCard>

        <QCard num={10} title="既有保障快篩">
          <div className="mb-4">
            <div className="text-xs text-gray-400 mb-2">醫療險（實支實付）大約額度</div>
            <div className="flex flex-wrap gap-2">{MEDICAL_OPTS.map((o) => <Chip key={o} selected={form.existing_medical_coverage === o} onClick={() => set("existing_medical_coverage", o)}>{o}</Chip>)}</div>
          </div>
          <div>
            <div className="text-xs text-gray-400 mb-2">長照 / 失能險每月給付</div>
            <div className="flex flex-wrap gap-2">{LTC_OPTS.map((o) => <Chip key={o} selected={form.existing_ltc_coverage === o} onClick={() => set("existing_ltc_coverage", o)}>{o}</Chip>)}</div>
          </div>
        </QCard>

        <QCard num={11} title="既有保單與同意接受資訊">
          <div className="mb-4">
            <div className="text-xs text-gray-400 mb-2">目前是否已有保險？</div>
            <div className="flex gap-2">
              <Chip selected={form.has_existing_insurance} onClick={() => set("has_existing_insurance", true)}>有</Chip>
              <Chip selected={!form.has_existing_insurance} onClick={() => set("has_existing_insurance", false)}>沒有</Chip>
            </div>
          </div>
          {form.has_existing_insurance && (
            <div className="space-y-3 mt-3">
              <div>
                <div className="text-xs text-gray-400 mb-2">既有保單類型（可複選）</div>
                <div className="flex flex-wrap gap-2">
                  {[["has_existing_life_insurance", "壽險"], ["has_existing_medical_insurance", "醫療險"], ["has_existing_accident_insurance", "傷害險"], ["has_existing_annuity", "年金險"], ["has_existing_savings_insurance", "儲蓄/投資型"]].map(([k, l]) => (
                    <Chip key={k} selected={Boolean(form[k as keyof QForm])} onClick={() => set(k as keyof QForm, !form[k as keyof QForm] as never)}>{l}</Chip>
                  ))}
                </div>
              </div>
              <div>
                <div className="text-xs text-gray-400 mb-2">現有保單簡述</div>
                <textarea rows={3} value={form.existing_policies_notes}
                  onChange={(e) => set("existing_policies_notes", e.target.value)}
                  placeholder="例如：已有壽險 200 萬、醫療險實支實付…"
                  className="w-full resize-none border border-gray-200 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-1 focus:ring-emerald-400" />
              </div>
            </div>
          )}
          <div className="mt-4 border-t border-gray-100 pt-4">
            <div className="text-xs text-gray-400 mb-2">同意接收理財資訊？</div>
            <div className="flex gap-2">
              <Chip selected={form.consent_advisory} onClick={() => set("consent_advisory", true)}>同意</Chip>
              <Chip selected={!form.consent_advisory} onClick={() => set("consent_advisory", false)}>不同意</Chip>
            </div>
          </div>
        </QCard>

        {error && <p className="text-red-500 text-sm">{error}</p>}

        <div className="flex gap-3">
          <Link href={`/advisor/clients/${id}`} className="flex-1 py-2.5 rounded-lg border border-gray-300 text-sm text-center text-gray-600 hover:bg-gray-50 transition-colors">
            返回
          </Link>
          <button onClick={handleSave} disabled={saving}
            className="flex-1 bg-emerald-600 hover:bg-emerald-700 disabled:opacity-50 text-white font-medium py-2.5 rounded-lg text-sm transition-colors">
            {saving ? "儲存中…" : saved ? "已儲存 ✓" : "儲存問卷"}
          </button>
        </div>
      </div>

      <footer className="mt-8 text-xs text-gray-400 text-center border-t border-gray-100 pt-4">
        本工具供業務員內部使用，非保險公司正式建議書。
      </footer>
    </div>
  );
}
