import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Save,
} from 'lucide-react';
import type { Client, Questionnaire } from '../../shared/types';
import { api, ApiError } from '../lib/api';
import ChatPanel from '../components/ChatPanel';
import TopBar from '../components/TopBar';

/* =========================================================================
   QuestionnaireForm.tsx — 退休規劃問卷（Notion / Linear 風）
   ========================================================================= */

const STEPS = [
  { key: 'basics', label: '基本資料', path: '' },
  { key: 'balance', label: '資產負債', path: 'balance-sheet' },
  { key: 'quiz', label: '退休問卷', path: 'questionnaire' },
  { key: 'simulate', label: '退休推演', path: 'simulator' },
  { key: 'compare', label: '個別模組總覽', path: 'strategy' },
] as const;

function StepNav({ clientId }: { clientId: string }) {
  return (
    <ol className="flex items-center gap-1 overflow-x-auto">
      {STEPS.map((s, i) => {
        const active = s.key === 'quiz';
        const to = s.path ? `/clients/${clientId}/${s.path}` : `/clients/${clientId}`;
        return (
          <li key={s.key} className="flex items-center">
            <Link
              to={to}
              className={[
                'flex items-center gap-2 rounded-lg px-3 py-1.5 text-[13px]',
                active
                  ? 'bg-neutral-900 text-white'
                  : 'text-neutral-500 hover:text-neutral-900',
              ].join(' ')}
            >
              <span
                className={[
                  'grid h-5 w-5 place-items-center rounded-full font-mono text-[10px]',
                  active
                    ? 'bg-white text-neutral-900'
                    : 'border border-neutral-300 text-neutral-400',
                ].join(' ')}
              >
                {active ? <Check className="h-3 w-3" strokeWidth={3} /> : i + 1}
              </span>
              <span>{s.label}</span>
            </Link>
            {i < STEPS.length - 1 && (
              <ChevronRight className="mx-0.5 h-3.5 w-3.5 text-neutral-300" strokeWidth={2} />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function Chip({
  selected,
  onClick,
  children,
}: {
  selected: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      onClick={onClick}
      className={[
        'rounded-lg border px-3 py-1.5 text-[13px] transition-colors',
        selected
          ? 'border-neutral-900 bg-neutral-900 text-white'
          : 'border-neutral-200 bg-white text-neutral-700 hover:border-neutral-400',
      ].join(' ')}
    >
      {children}
    </button>
  );
}

function QuestionCard({
  num,
  title,
  children,
}: {
  num: number;
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-neutral-200 bg-white p-6">
      <div className="mb-4 flex items-baseline gap-3">
        <span className="font-mono text-[11px] tracking-[0.18em] text-neutral-400">
          {String(num).padStart(2, '0')}
        </span>
        <h3 className="font-serif text-[17px] leading-snug text-neutral-900">{title}</h3>
      </div>
      {children}
    </section>
  );
}

const CHANNEL_OPTIONS = [
  '銀行存款',
  '外幣存款',
  '標會',
  '保險理財',
  '股票',
  '基金',
  '其他',
];
const INCOME_SOURCES = [
  '政府的老人年金',
  '社會團體的支援',
  '子女的奉養',
  '自己規劃的退休金',
];
const DREAM_OPTIONS = [
  '環遊世界',
  '學習新知',
  '公益活動',
  '發展事業第二春',
  '含飴弄孫',
  '協助子女成家立業',
  '其他',
];
const TOPIC_OPTIONS = [
  '個人儲蓄投資理財',
  '節稅資訊',
  '退休理財規劃',
  '房貸理財計劃',
];
const RISK_FACTORS = [
  '壽命延長',
  '失業率高',
  '稅賦負擔',
  '生活費用高',
  '醫療費用增加',
  '少子化',
  '離婚率高',
  '存款利率低',
  '投資風險高',
  '社會福利不足',
];
const RETIRE_AMOUNTS = [500, 700, 1000, 1500, 3000, 4200];
const MONTHLY_LIVING = [20000, 30000, 40000, 50000, 80000, 120000];
const MONTHLY_BUDGETS = [5000, 10000, 20000, 30000, 50000];

type ExistingInsuranceKey =
  | 'has_existing_life_insurance'
  | 'has_existing_medical_insurance'
  | 'has_existing_accident_insurance'
  | 'has_existing_annuity'
  | 'has_existing_savings_insurance';

const EXISTING_INSURANCE_CHIPS: { key: ExistingInsuranceKey; label: string }[] = [
  { key: 'has_existing_life_insurance', label: '壽險' },
  { key: 'has_existing_medical_insurance', label: '醫療險' },
  { key: 'has_existing_accident_insurance', label: '傷害險' },
  { key: 'has_existing_annuity', label: '年金險' },
  { key: 'has_existing_savings_insurance', label: '儲蓄/投資型' },
];

export default function QuestionnaireForm() {
  const { id } = useParams();
  const clientId = id ?? '';
  const navigate = useNavigate();
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [clientName, setClientName] = useState('');

  const [form, setForm] = useState<Partial<Questionnaire>>({
    preferred_channels: [],
    retire_income_sources: [],
    retire_dreams: [],
    retire_target_amount: 1000,
    retire_monthly_living: 40000,
    interested_topics: [],
    monthly_investable_budget: 10000,
    risk_factors: [],
    consent_advisory: true,
    has_existing_insurance: false,
    existing_policies_notes: '',
    health_status: '極佳',
    has_family_disease: false,
    existing_medical_coverage: '不清楚',
    existing_ltc_coverage: '不清楚',
  });

  useEffect(() => {
    if (!id) return;
    api
      .get<Client>(`/api/clients/${id}`)
      .then((c) => setClientName(c.name))
      .catch(() => {});
    api
      .get<Questionnaire | null>(`/api/questionnaires/${id}`)
      .then((data) => {
        if (data) setForm(data);
      })
      .catch(() => {})
      .finally(() => setLoading(false));
  }, [id]);

  const toggleMulti = (field: keyof Questionnaire, value: string) => {
    setForm((prev) => {
      const arr = (prev[field] as string[]) || [];
      const next = arr.includes(value) ? arr.filter((v) => v !== value) : [...arr, value];
      return { ...prev, [field]: next };
    });
  };

  const set = <K extends keyof Questionnaire>(k: K, v: Questionnaire[K]) =>
    setForm((prev) => ({ ...prev, [k]: v }));

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      await api.put(`/api/questionnaires/${id}`, form);
      setSaved(true);
      setTimeout(() => navigate(`/clients/${id}/simulator`), 600);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '儲存失敗');
      setSaving(false);
    }
  };

  return (
    <div
      className="min-h-screen text-[var(--text-primary)] antialiased"
      style={{
        background: 'var(--surface-bg)',
        fontFamily:
          '"Noto Sans TC", ui-sans-serif, system-ui, -apple-system, sans-serif',
      }}
    >
      <TopBar
        breadcrumb={[
          { label: '工作台', to: '/' },
          { label: '客戶', to: '/clients' },
          { label: clientName || '—', to: `/clients/${clientId}` },
          { label: '退休問卷' },
        ]}
      />

      <div
        className="no-print sticky top-[81px] z-20 border-b backdrop-blur"
        style={{
          background: 'rgba(255, 248, 238, 0.85)',
          borderColor: 'var(--border-subtle)',
        }}
      >
        <div className="mx-auto flex max-w-[1200px] items-center justify-between gap-3 px-6 py-3">
          <StepNav clientId={clientId} />
          <div className="flex items-center gap-3">
            {saved && (
              <span
                className="flex items-center gap-1.5 text-[13px]"
                style={{ color: 'var(--accent-success)' }}
              >
                <CheckCircle2 className="h-4 w-4" /> 已儲存
              </span>
            )}
            <button
              onClick={handleSubmit}
              disabled={saving}
              className="btn-primary inline-flex shrink-0 items-center gap-2 rounded-lg px-4 py-2 text-[14px] disabled:opacity-50"
            >
              <Save className="h-4 w-4" strokeWidth={2} />
              {saving ? '儲存中…' : '儲存問卷'}
            </button>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-[1040px] px-6 py-10 md:py-12">
        <div
          className="mb-8 border-l-4 pl-4"
          style={{ borderColor: 'var(--accent-primary)' }}
        >
          <h1 className="text-section-title">退休規劃問卷</h1>
          <p className="mt-2 text-section-sub">
            協助釐清客戶的退休想像、風險認知與既有保障。儲存後會自動前往「退休推演」。
          </p>
        </div>

        {error && (
          <div className="mb-6 flex items-start gap-3 rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-800">
            <AlertTriangle className="mt-0.5 h-4 w-4 shrink-0" />
            <span>{error}</span>
          </div>
        )}

        {loading ? (
          <div className="rounded-xl border border-neutral-200 bg-white py-16 text-center text-sm text-neutral-400">
            載入中…
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-5">
            <QuestionCard
              num={1}
              title="您喜歡選擇哪些投資理財管道來增加個人財富？（可複選）"
            >
              <div className="flex flex-wrap gap-2">
                {CHANNEL_OPTIONS.map((opt) => (
                  <Chip
                    key={opt}
                    selected={form.preferred_channels?.includes(opt) || false}
                    onClick={() => toggleMulti('preferred_channels', opt)}
                  >
                    {opt}
                  </Chip>
                ))}
              </div>
            </QuestionCard>

            <QuestionCard
              num={2}
              title="您認為最有保障的退休收入是什麼？（可複選）"
            >
              <div className="flex flex-wrap gap-2">
                {INCOME_SOURCES.map((opt) => (
                  <Chip
                    key={opt}
                    selected={form.retire_income_sources?.includes(opt) || false}
                    onClick={() => toggleMulti('retire_income_sources', opt)}
                  >
                    {opt}
                  </Chip>
                ))}
              </div>
            </QuestionCard>

            <QuestionCard num={3} title="退休後想做哪些事？（可複選）">
              <div className="flex flex-wrap gap-2">
                {DREAM_OPTIONS.map((opt) => (
                  <Chip
                    key={opt}
                    selected={form.retire_dreams?.includes(opt) || false}
                    onClick={() => toggleMulti('retire_dreams', opt)}
                  >
                    {opt}
                  </Chip>
                ))}
              </div>
            </QuestionCard>

            <QuestionCard num={4} title="退休後到底要準備多少退休金才夠用？">
              <div className="flex flex-wrap gap-2">
                {RETIRE_AMOUNTS.map((amt) => (
                  <Chip
                    key={amt}
                    selected={form.retire_target_amount === amt}
                    onClick={() => set('retire_target_amount', amt)}
                  >
                    {amt} 萬
                  </Chip>
                ))}
              </div>
              <div className="mt-4 flex items-center gap-3">
                <span className="font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                  自訂
                </span>
                <input
                  type="number"
                  value={form.retire_target_amount ?? 0}
                  min={0}
                  onChange={(e) =>
                    set('retire_target_amount', Number(e.target.value) || 0)
                  }
                  className="w-32 rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-right text-sm tabular-nums text-neutral-900 focus:border-neutral-900 focus:outline-none"
                />
                <span className="text-[12px] text-neutral-500">萬元</span>
              </div>
            </QuestionCard>

            <QuestionCard num={5} title="退休後每個月的生活費希望是多少？">
              <div className="flex flex-wrap gap-2">
                {MONTHLY_LIVING.map((amt) => (
                  <Chip
                    key={amt}
                    selected={form.retire_monthly_living === amt}
                    onClick={() => set('retire_monthly_living', amt)}
                  >
                    {(amt / 10000).toFixed(0)} 萬元
                  </Chip>
                ))}
              </div>
              <div className="mt-4 flex items-center gap-3">
                <span className="font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                  自訂
                </span>
                <input
                  type="number"
                  value={form.retire_monthly_living ?? 0}
                  min={0}
                  step={1000}
                  onChange={(e) =>
                    set('retire_monthly_living', Number(e.target.value) || 0)
                  }
                  className="w-36 rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-right text-sm tabular-nums text-neutral-900 focus:border-neutral-900 focus:outline-none"
                />
                <span className="text-[12px] text-neutral-500">元</span>
              </div>
            </QuestionCard>

            <QuestionCard num={6} title="希望了解的理財資訊（可複選）">
              <div className="flex flex-wrap gap-2">
                {TOPIC_OPTIONS.map((opt) => (
                  <Chip
                    key={opt}
                    selected={form.interested_topics?.includes(opt) || false}
                    onClick={() => toggleMulti('interested_topics', opt)}
                  >
                    {opt}
                  </Chip>
                ))}
              </div>
            </QuestionCard>

            <QuestionCard num={7} title="每月可提撥多少用於儲蓄或投資？">
              <div className="flex flex-wrap gap-2">
                {MONTHLY_BUDGETS.map((amt) => (
                  <Chip
                    key={amt}
                    selected={form.monthly_investable_budget === amt}
                    onClick={() => set('monthly_investable_budget', amt)}
                  >
                    {amt >= 10000
                      ? `${(amt / 10000).toFixed(0)} 萬元`
                      : `${amt.toLocaleString()} 元`}
                  </Chip>
                ))}
                <Chip
                  selected={(form.monthly_investable_budget || 0) > 50000}
                  onClick={() => set('monthly_investable_budget', 60000)}
                >
                  5 萬以上
                </Chip>
              </div>
              <div className="mt-4 flex items-center gap-3">
                <span className="font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                  自訂
                </span>
                <input
                  type="number"
                  value={form.monthly_investable_budget ?? 0}
                  min={0}
                  step={1000}
                  onChange={(e) =>
                    set('monthly_investable_budget', Number(e.target.value) || 0)
                  }
                  className="w-36 rounded-lg border border-neutral-200 bg-white px-3 py-1.5 text-right text-sm tabular-nums text-neutral-900 focus:border-neutral-900 focus:outline-none"
                />
                <span className="text-[12px] text-neutral-500">元 / 月</span>
              </div>
            </QuestionCard>

            <QuestionCard num={8} title="會影響您準備退休金的因素？（可複選）">
              <div className="flex flex-wrap gap-2">
                {RISK_FACTORS.map((opt) => (
                  <Chip
                    key={opt}
                    selected={form.risk_factors?.includes(opt) || false}
                    onClick={() => toggleMulti('risk_factors', opt)}
                  >
                    {opt}
                  </Chip>
                ))}
              </div>
            </QuestionCard>

            <QuestionCard num={9} title="客戶自評健康狀況與家族病史">
              <div className="mb-5">
                <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                  健康狀況
                </div>
                <div className="flex flex-wrap gap-2">
                  {['極佳', '良好', '有定期服藥', '有重大病史', '曾有拒保紀錄'].map(
                    (opt) => (
                      <Chip
                        key={opt}
                        selected={form.health_status === opt}
                        onClick={() => set('health_status', opt)}
                      >
                        {opt}
                      </Chip>
                    ),
                  )}
                </div>
              </div>
              <div>
                <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                  直系親屬是否有重大遺傳疾病或家族病史？
                </div>
                <div className="flex gap-2">
                  <Chip
                    selected={form.has_family_disease === true}
                    onClick={() => set('has_family_disease', true)}
                  >
                    是
                  </Chip>
                  <Chip
                    selected={form.has_family_disease === false}
                    onClick={() => set('has_family_disease', false)}
                  >
                    否
                  </Chip>
                </div>
              </div>
            </QuestionCard>

            <QuestionCard num={10} title="既有保障快篩（醫療與長照）">
              <div className="mb-5">
                <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                  醫療險（實支實付）大約額度
                </div>
                <div className="flex flex-wrap gap-2">
                  {['無', '不清楚', '5 萬以內', '10 萬左右', '20 萬以上'].map((opt) => (
                    <Chip
                      key={opt}
                      selected={form.existing_medical_coverage === opt}
                      onClick={() => set('existing_medical_coverage', opt)}
                    >
                      {opt}
                    </Chip>
                  ))}
                </div>
              </div>
              <div>
                <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                  長照 / 失能險 大約每月給付
                </div>
                <div className="flex flex-wrap gap-2">
                  {['無', '不清楚', '2 萬以內', '3~4 萬', '5 萬以上'].map((opt) => (
                    <Chip
                      key={opt}
                      selected={form.existing_ltc_coverage === opt}
                      onClick={() => set('existing_ltc_coverage', opt)}
                    >
                      {opt}
                    </Chip>
                  ))}
                </div>
              </div>
            </QuestionCard>

            <QuestionCard num={11} title="同意接收一份專屬的理財資訊？">
              <div className="mb-5 flex gap-2">
                <Chip
                  selected={form.consent_advisory === true}
                  onClick={() => set('consent_advisory', true)}
                >
                  好
                </Chip>
                <Chip
                  selected={form.consent_advisory === false}
                  onClick={() => set('consent_advisory', false)}
                >
                  不好
                </Chip>
              </div>

              <div className="border-t border-neutral-100 pt-5">
                <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                  目前是否已有保險？
                </div>
                <div className="flex gap-2">
                  <Chip
                    selected={form.has_existing_insurance === true}
                    onClick={() => set('has_existing_insurance', true)}
                  >
                    有
                  </Chip>
                  <Chip
                    selected={form.has_existing_insurance === false}
                    onClick={() => set('has_existing_insurance', false)}
                  >
                    沒有
                  </Chip>
                </div>

                {form.has_existing_insurance && (
                  <div className="mt-5 space-y-4">
                    <div>
                      <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                        既有保單類型（可複選）
                      </div>
                      <div className="flex flex-wrap gap-2">
                        {EXISTING_INSURANCE_CHIPS.map(({ key, label }) => {
                          const checked = Boolean(form[key]);
                          return (
                            <Chip
                              key={key}
                              selected={checked}
                              onClick={() => setForm((p) => ({ ...p, [key]: !checked }))}
                            >
                              {label}
                            </Chip>
                          );
                        })}
                      </div>
                    </div>
                    <div>
                      <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                        現有保單簡述
                      </div>
                      <textarea
                        rows={3}
                        value={form.existing_policies_notes ?? ''}
                        onChange={(e) =>
                          set('existing_policies_notes', e.target.value)
                        }
                        placeholder="例如：已有壽險 200 萬、醫療險實支實付…"
                        className="w-full resize-none rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 focus:border-neutral-900 focus:outline-none"
                      />
                    </div>
                  </div>
                )}
              </div>
            </QuestionCard>

            <div className="flex items-center justify-between border-t border-neutral-200 pt-6">
              <Link
                to={`/clients/${clientId}/balance-sheet`}
                className="text-[13px] text-neutral-500 hover:text-neutral-900"
              >
                ← 返回資產負債
              </Link>
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg bg-neutral-900 px-5 py-2.5 text-[13px] font-medium text-white transition-colors hover:bg-neutral-800 disabled:opacity-50"
              >
                {saving ? '儲存中…' : '儲存並前往退休推演'}
                <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
              </button>
            </div>
          </form>
        )}

        <footer className="mt-16 flex flex-wrap items-center justify-between gap-3 border-t border-neutral-200 pt-6 font-mono text-[11px] text-neutral-400">
          <span>© 2026 退休規劃</span>
          <span>保經內部試算工具 · 非保險公司建議書</span>
        </footer>
      </main>

      <ChatPanel />
    </div>
  );
}
