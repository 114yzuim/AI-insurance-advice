import { useEffect, useState } from 'react';
import { Link, useNavigate, useParams } from 'react-router-dom';
import {
  ArrowRight,
  Check,
  ChevronRight,
  HeartPulse,
  Save,
  Shield,
  TrendingUp,
} from 'lucide-react';
import type { Client, ModuleCode } from '../../shared/types';
import { api, ApiError } from '../lib/api';
import ChatPanel from '../components/ChatPanel';
import TopBar from '../components/TopBar';

/* =========================================================================
   ClientForm.tsx — 新增 / 編輯客戶（Notion / Linear 風）
   ========================================================================= */

const STEPS = [
  { key: 'basics', label: '基本資料', path: '' },
  { key: 'balance', label: '資產負債', path: 'balance-sheet' },
  { key: 'quiz', label: '退休問卷', path: 'questionnaire' },
  { key: 'simulate', label: '退休推演', path: 'simulator' },
  { key: 'compare', label: '個別模組總覽', path: 'strategy' },
] as const;

function StepNav({ clientId }: { clientId: string | null }) {
  return (
    <ol className="flex items-center gap-1 overflow-x-auto">
      {STEPS.map((s, i) => {
        const active = s.key === 'basics';
        const disabled = clientId == null && !active;
        const to = clientId
          ? s.path
            ? `/clients/${clientId}/${s.path}`
            : `/clients/${clientId}`
          : '#';
        return (
          <li key={s.key} className="flex items-center">
            {disabled ? (
              <span
                className="flex items-center gap-2 rounded-lg px-3 py-1.5 text-[13px] text-neutral-300"
                title="儲存客戶後才可進入"
              >
                <span className="grid h-5 w-5 place-items-center rounded-full border border-neutral-200 font-mono text-[10px]">
                  {i + 1}
                </span>
                <span>{s.label}</span>
              </span>
            ) : (
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
            )}
            {i < STEPS.length - 1 && (
              <ChevronRight
                className="mx-0.5 h-3.5 w-3.5 text-neutral-300"
                strokeWidth={2}
              />
            )}
          </li>
        );
      })}
    </ol>
  );
}

function SectionLabel({ num, children }: { num: string; children: React.ReactNode }) {
  return (
    <div className="mb-3 flex items-baseline gap-3">
      <span className="font-mono text-[11px] tracking-[0.18em] text-neutral-400">{num}</span>
      <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-neutral-500">
        {children}
      </span>
    </div>
  );
}

function TextIn({
  label,
  value,
  onChange,
  type = 'text',
  placeholder,
  required,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  type?: 'text' | 'tel';
  placeholder?: string;
  required?: boolean;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-neutral-500">
        {label}
        {required && <span className="ml-0.5 text-rose-500">*</span>}
      </span>
      <input
        type={type}
        value={value}
        placeholder={placeholder}
        required={required}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 placeholder:text-neutral-400 transition-colors focus:border-neutral-900 focus:outline-none"
      />
    </label>
  );
}

function NumIn({
  label,
  value,
  onChange,
  unit,
  min,
  max,
  step = 1,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
  unit?: string;
  min?: number;
  max?: number;
  step?: number;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-neutral-500">
        {label}
      </span>
      <div className="flex items-center rounded-lg border border-neutral-200 bg-white transition-colors focus-within:border-neutral-900">
        <input
          type="number"
          value={Number.isFinite(value) ? value : 0}
          min={min}
          max={max}
          step={step}
          onChange={(e) => onChange(Number(e.target.value))}
          className="w-full bg-transparent px-3 py-2 text-sm tabular-nums text-neutral-900 focus:outline-none"
        />
        {unit && <span className="pr-3 font-mono text-[11px] text-neutral-400">{unit}</span>}
      </div>
    </label>
  );
}

function SelIn({
  label,
  value,
  onChange,
  children,
}: {
  label: string;
  value: string;
  onChange: (v: string) => void;
  children: React.ReactNode;
}) {
  return (
    <label className="block">
      <span className="mb-1.5 block text-[11px] font-medium uppercase tracking-wider text-neutral-500">
        {label}
      </span>
      <select
        value={value}
        onChange={(e) => onChange(e.target.value)}
        className="w-full rounded-lg border border-neutral-200 bg-white px-3 py-2 text-sm text-neutral-900 transition-colors focus:border-neutral-900 focus:outline-none"
      >
        {children}
      </select>
    </label>
  );
}

const MODULES: { code: ModuleCode; label: string; sub: string; Icon: typeof TrendingUp }[] = [
  { code: 'A', label: '投資', sub: 'ETF · 股債', Icon: TrendingUp },
  { code: 'B', label: '保險', sub: '年金 · 壽險', Icon: Shield },
  { code: 'C', label: '失能長照', sub: '失能扶助 · 長照險', Icon: HeartPulse },
];

const PLAN_GOALS = [
  { key: 'protection', label: '純保障', desc: '高槓桿壽險' },
  { key: 'savings', label: '資產儲蓄', desc: '重內部報酬率' },
  { key: 'legacy', label: '財富傳承', desc: '預留稅源' },
  { key: 'healthcare', label: '醫療照護', desc: '長照 / 醫療' },
] as const;

export default function ClientForm() {
  const { id } = useParams();
  const navigate = useNavigate();
  const isEdit = Boolean(id);

  const [loading, setLoading] = useState(isEdit);
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);

  const [form, setForm] = useState<Partial<Client>>({
    name: '',
    phone: '',
    age: 30,
    gender: '男',
    family_status: '單身',
    children_count: 0,
    occupation: '',
    target_retire_age: 65,
    life_expectancy: 85,
    risk_tolerance: 'moderate',
    planning_goals: [],
    selected_modules: ['A'] as ModuleCode[],
    is_joint_plan: false,
    spouse_name: '',
    spouse_age: 30,
    spouse_gender: '女',
    spouse_retire_age: 65,
    spouse_life_expectancy: 85,
  });

  useEffect(() => {
    if (!isEdit) return;
    api
      .get<Client>(`/api/clients/${id}`)
      .then((c) => setForm(c))
      .catch(() => setError('無法載入客戶資料。'))
      .finally(() => setLoading(false));
  }, [id, isEdit]);

  const set = <K extends keyof Client>(k: K, v: Client[K]) =>
    setForm((prev) => ({ ...prev, [k]: v }));

  const toggleGoal = (goal: string) => {
    const curr = (form.planning_goals as string[]) || [];
    set(
      'planning_goals',
      curr.includes(goal) ? curr.filter((g) => g !== goal) : [...curr, goal],
    );
  };

  const toggleModule = (code: ModuleCode) => {
    const curr = (form.selected_modules as ModuleCode[]) || [];
    const next = curr.includes(code) ? curr.filter((m) => m !== code) : [...curr, code];
    set('selected_modules', (next.length > 0 ? next : curr) as ModuleCode[]);
  };

  /**
   * Sanitize the Client payload before send.
   * - GET response has nulls on nullable array fields (planning_goals) → Pydantic rejects
   * - Money columns come back as numeric strings → coerce to number
   * - Drop fields that aren't part of the write schema (id, status, *_at)
   */
  const sanitize = (c: Partial<Client>): Record<string, unknown> => {
    const numericKeys = [
      'monthly_income',
      'monthly_expense',
      'current_assets',
      'current_liabilities',
      'monthly_investable',
      'target_retire_monthly_expense',
      'existing_insurance_annual',
    ];
    const out: Record<string, unknown> = {};
    for (const [k, v] of Object.entries(c)) {
      if (k === 'id' || k === 'user_id' || k === 'status') continue;
      if (k === 'created_at' || k === 'updated_at') continue;
      if (v === undefined) continue;
      if (k === 'planning_goals' || k === 'children_ages') {
        out[k] = Array.isArray(v) ? v : [];
        continue;
      }
      if (k === 'selected_modules') {
        out[k] = Array.isArray(v) && v.length > 0 ? v : ['A'];
        continue;
      }
      if (numericKeys.includes(k)) {
        out[k] = v === null || v === '' ? 0 : Number(v);
        continue;
      }
      out[k] = v;
    }
    return out;
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    setSaving(true);
    setError(null);
    try {
      const payload = sanitize(form);
      if (isEdit) {
        await api.put(`/api/clients/${id}`, payload);
        navigate(`/clients/${id}/balance-sheet`);
      } else {
        const created = await api.post<{ id: number }>('/api/clients', payload);
        navigate(`/clients/${created.id}/balance-sheet`);
      }
    } catch (err) {
      const msg =
        err instanceof ApiError ? err.message : '儲存失敗，請確認資料庫連線正常。';
      setError(msg);
      setSaving(false);
    }
  };

  const isMarried =
    form.family_status === '已婚' || form.family_status === '已婚有子女';

  const yearsToRetire = (form.target_retire_age ?? 0) - (form.age ?? 0);
  const retireYears = (form.life_expectancy ?? 0) - (form.target_retire_age ?? 0);
  const totalYears = (form.life_expectancy ?? 0) - (form.age ?? 0);

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
          { label: isEdit ? form.name || '—' : '新增客戶' },
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
          <StepNav clientId={id ?? null} />
          <button
            type="button"
            onClick={handleSubmit}
            disabled={saving}
            className="btn-primary inline-flex shrink-0 items-center gap-2 rounded-lg px-4 py-2 text-[14px] disabled:opacity-50"
          >
            <Save className="h-4 w-4" strokeWidth={2} />
            {saving ? '儲存中…' : isEdit ? '儲存資料' : '建立客戶'}
          </button>
        </div>
      </div>

      <main className="mx-auto max-w-[1040px] px-6 py-10 md:py-12">
        {/* title — 暮霞風 */}
        <div
          className="mb-8 border-l-4 pl-4"
          style={{ borderColor: 'var(--accent-primary)' }}
        >
          <h1 className="text-section-title">
            {isEdit ? '編輯客戶資料' : '新增客戶資料'}
          </h1>
          <p className="mt-2 text-section-sub">
            填寫客戶基本背景與退休目標。儲存後會自動跳到「資產負債」頁。
          </p>
        </div>

        {loading ? (
          <div className="rounded-xl border border-neutral-200 bg-white py-16 text-center text-sm text-neutral-400">
            載入中…
          </div>
        ) : (
          <form onSubmit={handleSubmit} className="space-y-10">
            {error && (
              <div className="rounded-lg border border-red-200 bg-red-50 px-4 py-3 text-[13px] text-red-800">
                {error}
              </div>
            )}

            {/* 01 基本資料 */}
            <section className="rounded-xl border border-neutral-200 bg-white p-6">
              <SectionLabel num="01">基本資料</SectionLabel>
              <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                <TextIn
                  label="客戶姓名"
                  required
                  value={form.name ?? ''}
                  onChange={(v) => set('name', v)}
                  placeholder="例如：王小明"
                />
                <TextIn
                  label="聯絡電話"
                  type="tel"
                  value={form.phone ?? ''}
                  onChange={(v) => set('phone', v)}
                  placeholder="0912-345-678"
                />
                <NumIn
                  label="目前年齡"
                  value={form.age ?? 30}
                  onChange={(v) => set('age', v)}
                  unit="歲"
                  min={18}
                  max={100}
                />
                <SelIn
                  label="性別"
                  value={form.gender ?? '男'}
                  onChange={(v) => set('gender', v)}
                >
                  <option value="男">男性</option>
                  <option value="女">女性</option>
                  <option value="其他">其他</option>
                </SelIn>
                <SelIn
                  label="婚姻狀況"
                  value={form.family_status ?? '單身'}
                  onChange={(v) => set('family_status', v)}
                >
                  <option value="單身">未婚</option>
                  <option value="已婚">已婚</option>
                  <option value="已婚有子女">已婚有子女</option>
                  <option value="離婚">離婚</option>
                  <option value="喪偶">喪偶</option>
                </SelIn>
                <NumIn
                  label="子女數"
                  value={form.children_count ?? 0}
                  onChange={(v) => set('children_count', v)}
                  min={0}
                  max={10}
                />
                <div className="md:col-span-2">
                  <TextIn
                    label="職業"
                    value={form.occupation ?? ''}
                    onChange={(v) => set('occupation', v)}
                    placeholder="例如：上班族、自營業者"
                  />
                </div>
              </div>
            </section>

            {/* 02 配偶（僅已婚） */}
            {isMarried && (
              <section className="rounded-xl border border-neutral-200 bg-white p-6">
                <div className="mb-3 flex items-center justify-between">
                  <SectionLabel num="02">配偶資料（聯合規劃）</SectionLabel>
                  <label className="flex cursor-pointer items-center gap-2 text-[13px] text-neutral-700">
                    <input
                      type="checkbox"
                      checked={form.is_joint_plan || false}
                      onChange={(e) => set('is_joint_plan', e.target.checked)}
                      className="h-4 w-4 accent-neutral-900"
                    />
                    啟用聯合規劃
                  </label>
                </div>

                {form.is_joint_plan && (
                  <div className="grid grid-cols-1 gap-5 md:grid-cols-2">
                    <TextIn
                      label="配偶姓名"
                      value={form.spouse_name ?? ''}
                      onChange={(v) => set('spouse_name', v)}
                      placeholder="例如：林小華"
                    />
                    <NumIn
                      label="目前年齡"
                      value={form.spouse_age ?? 30}
                      onChange={(v) => set('spouse_age', v)}
                      unit="歲"
                      min={18}
                      max={100}
                    />
                    <SelIn
                      label="配偶性別"
                      value={form.spouse_gender ?? '女'}
                      onChange={(v) => set('spouse_gender', v)}
                    >
                      <option value="男">男性</option>
                      <option value="女">女性</option>
                      <option value="其他">其他</option>
                    </SelIn>
                    <NumIn
                      label="預計退休年齡"
                      value={form.spouse_retire_age ?? 65}
                      onChange={(v) => set('spouse_retire_age', v)}
                      unit="歲"
                      min={40}
                      max={80}
                    />
                    <NumIn
                      label="預估平均餘命"
                      value={form.spouse_life_expectancy ?? 85}
                      onChange={(v) => set('spouse_life_expectancy', v)}
                      unit="歲"
                      min={60}
                      max={110}
                    />
                  </div>
                )}
              </section>
            )}

            {/* 03 退休目標 */}
            <section className="rounded-xl border border-neutral-200 bg-white p-6">
              <SectionLabel num={isMarried ? '03' : '02'}>退休目標</SectionLabel>
              <div className="grid grid-cols-1 gap-5 md:grid-cols-3">
                <NumIn
                  label="預計退休年齡"
                  value={form.target_retire_age ?? 65}
                  onChange={(v) => set('target_retire_age', v)}
                  unit="歲"
                  min={40}
                  max={80}
                />
                <NumIn
                  label="預估平均餘命"
                  value={form.life_expectancy ?? 85}
                  onChange={(v) => set('life_expectancy', v)}
                  unit="歲"
                  min={60}
                  max={110}
                />
                <SelIn
                  label="可承受單年最大跌幅"
                  value={form.risk_tolerance ?? 'moderate'}
                  onChange={(v) => set('risk_tolerance', v)}
                >
                  <option value="conservative">低（約 -10% 內）</option>
                  <option value="moderate">中（約 -20% 內）</option>
                  <option value="aggressive">高（可承受 -30% 以上）</option>
                </SelIn>
              </div>

              {totalYears > 0 && (
                <div className="mt-5 grid grid-cols-3 gap-px overflow-hidden rounded-lg border border-neutral-200 bg-neutral-100">
                  <div className="bg-white px-4 py-3">
                    <div className="font-mono text-[10px] uppercase tracking-wider text-neutral-400">
                      距退休
                    </div>
                    <div
                      className="mt-1 font-serif tabular-nums text-neutral-900"
                      style={{ fontSize: 20, letterSpacing: '-0.01em' }}
                    >
                      {yearsToRetire} 年
                    </div>
                  </div>
                  <div className="bg-white px-4 py-3">
                    <div className="font-mono text-[10px] uppercase tracking-wider text-neutral-400">
                      退休生活
                    </div>
                    <div
                      className="mt-1 font-serif tabular-nums text-neutral-900"
                      style={{ fontSize: 20, letterSpacing: '-0.01em' }}
                    >
                      {retireYears} 年
                    </div>
                  </div>
                  <div className="bg-white px-4 py-3">
                    <div className="font-mono text-[10px] uppercase tracking-wider text-neutral-400">
                      預估餘命
                    </div>
                    <div
                      className="mt-1 font-serif tabular-nums text-neutral-900"
                      style={{ fontSize: 20, letterSpacing: '-0.01em' }}
                    >
                      {totalYears} 年
                    </div>
                  </div>
                </div>
              )}

              <div className="mt-6">
                <div className="mb-2 font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                  規劃目標 · 可複選
                </div>
                <div className="flex flex-wrap gap-2">
                  {PLAN_GOALS.map(({ key, label, desc }) => {
                    const selected =
                      ((form.planning_goals as string[]) || []).includes(key);
                    return (
                      <button
                        key={key}
                        type="button"
                        onClick={() => toggleGoal(key)}
                        className={[
                          'flex flex-col items-start rounded-lg border px-3 py-2 text-left transition-colors',
                          selected
                            ? 'border-neutral-900 bg-neutral-900 text-white'
                            : 'border-neutral-200 bg-white text-neutral-700 hover:border-neutral-400',
                        ].join(' ')}
                      >
                        <span className="text-[13px] font-medium">{label}</span>
                        <span
                          className={[
                            'text-[11px]',
                            selected ? 'text-white/70' : 'text-neutral-500',
                          ].join(' ')}
                        >
                          {desc}
                        </span>
                      </button>
                    );
                  })}
                </div>
              </div>
            </section>

            {/* 04 模組選擇 */}
            <section className="rounded-xl border border-neutral-200 bg-white p-6">
              <SectionLabel num={isMarried ? '04' : '03'}>規劃模組</SectionLabel>
              <p className="mb-4 text-[13px] text-neutral-500">
                決定推演器與個別模組總覽頁面顯示的內容。可複選，至少保留一個。
              </p>
              <div className="grid grid-cols-1 gap-3 md:grid-cols-3">
                {MODULES.map(({ code, label, sub, Icon }) => {
                  const selected = ((form.selected_modules as ModuleCode[]) || []).includes(
                    code,
                  );
                  return (
                    <button
                      key={code}
                      type="button"
                      onClick={() => toggleModule(code)}
                      className={[
                        'group flex items-start gap-3 rounded-xl border p-4 text-left transition-all',
                        selected
                          ? 'border-neutral-900 bg-neutral-900/[0.02]'
                          : 'border-neutral-200 bg-white hover:border-neutral-300',
                      ].join(' ')}
                    >
                      <span
                        className={[
                          'mt-0.5 inline-flex h-5 w-5 shrink-0 items-center justify-center rounded-md border',
                          selected
                            ? 'border-neutral-900 bg-neutral-900 text-white'
                            : 'border-neutral-300 bg-white text-transparent',
                        ].join(' ')}
                      >
                        <Check className="h-3 w-3" strokeWidth={3.5} />
                      </span>
                      <div className="min-w-0 flex-1">
                        <div className="flex items-baseline gap-2">
                          <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded border border-neutral-200 bg-white px-1 font-mono text-[11px] font-medium text-neutral-600">
                            {code}
                          </span>
                          <span className="font-medium text-neutral-900">{label}</span>
                        </div>
                        <div className="mt-0.5 text-[11.5px] text-neutral-500">{sub}</div>
                      </div>
                      <Icon
                        className={[
                          'h-4 w-4 shrink-0',
                          selected ? 'text-neutral-900' : 'text-neutral-400',
                        ].join(' ')}
                        strokeWidth={1.75}
                      />
                    </button>
                  );
                })}
              </div>
            </section>

            {/* bottom actions */}
            <div className="flex items-center justify-between border-t border-neutral-200 pt-6">
              <Link
                to={isEdit ? `/clients` : '/'}
                className="text-[13px] text-neutral-500 hover:text-neutral-900"
              >
                ← 返回
              </Link>
              <button
                type="submit"
                disabled={saving}
                className="inline-flex items-center gap-2 rounded-lg bg-neutral-900 px-5 py-2.5 text-[13px] font-medium text-white transition-colors hover:bg-neutral-800 disabled:opacity-50"
              >
                {saving ? '儲存中…' : '儲存並前往資產負債表'}
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

      {isEdit && <ChatPanel />}
    </div>
  );
}
