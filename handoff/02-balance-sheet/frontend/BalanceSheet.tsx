import { useCallback, useEffect, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  AlertTriangle,
  ArrowRight,
  Check,
  CheckCircle2,
  ChevronRight,
  Save,
} from 'lucide-react';
import type {
  BalanceSheetAssets,
  BalanceSheetLiabilities,
  Client,
  FixedDebtSlot,
} from '../../shared/types';
import { api, ApiError } from '../lib/api';
import { formatTwd } from '../lib/utils';
import ChatPanel from '../components/ChatPanel';
import TopBar from '../components/TopBar';
import {
  ASSET_SECTIONS,
  DEBT_KEYS,
  ES,
  GENERAL_FIELDS,
  emptyAssets,
  emptyLiabilities,
} from './BalanceSheet.constants';

/* =========================================================================
   BalanceSheet.tsx — 客戶資產負債表（Notion / Linear 風）
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
        const active = s.key === 'balance';
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

function AmountRow({
  label,
  value,
  onChange,
}: {
  label: string;
  value: number;
  onChange: (v: number) => void;
}) {
  return (
    <div className="flex items-center gap-3 py-1">
      <span className="w-44 shrink-0 truncate text-[13px] text-neutral-600" title={label}>
        {label}
      </span>
      <input
        type="number"
        value={value || ''}
        onChange={(e) => onChange(Number(e.target.value) || 0)}
        className="flex-1 rounded-md border border-neutral-200 bg-white px-2.5 py-1.5 text-right text-[13px] tabular-nums text-neutral-900 placeholder:text-neutral-300 focus:border-neutral-900 focus:outline-none"
        min={0}
        placeholder="0"
      />
    </div>
  );
}

function Hero({
  label,
  value,
  tone = 'neutral',
}: {
  label: string;
  value: number;
  tone?: 'neutral' | 'pos' | 'neg';
}) {
  const toneCls =
    tone === 'pos'
      ? 'border-emerald-200 bg-emerald-50/60 text-emerald-900'
      : tone === 'neg'
      ? 'border-rose-200 bg-rose-50/60 text-rose-900'
      : 'border-neutral-200 bg-white text-neutral-900';
  return (
    <div className={['rounded-xl border p-3', toneCls].join(' ')}>
      <div className="font-mono text-[10px] uppercase tracking-wider opacity-70">{label}</div>
      <div className="mt-1 font-mono tabular-nums text-[14px] font-semibold">
        {formatTwd(value)}
      </div>
    </div>
  );
}

export default function BalanceSheet() {
  const { id } = useParams();
  const clientId = id ?? '';
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [saved, setSaved] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [clientName, setClientName] = useState('');
  const [assets, setAssets] = useState<BalanceSheetAssets>(emptyAssets);
  const [liabilities, setLiabilities] = useState<BalanceSheetLiabilities>(emptyLiabilities);

  useEffect(() => {
    if (!id) return;
    Promise.all([
      api.get<Client>(`/api/clients/${id}`),
      api.get<{
        assets?: Partial<Record<keyof BalanceSheetAssets, unknown>>;
        liabilities?: {
          fixed?: Record<string, Partial<FixedDebtSlot>>;
          general?: Record<string, number>;
        };
      } | null>(`/api/clients/${id}/balance-sheet`),
    ])
      .then(([client, bs]) => {
        setClientName(client.name || '');
        if (bs) {
          const a = (bs.assets ?? {}) as Partial<BalanceSheetAssets>;
          setAssets({
            cash: { ...emptyAssets.cash, ...(a.cash ?? {}) },
            investment: { ...emptyAssets.investment, ...(a.investment ?? {}) },
            movable: { ...emptyAssets.movable, ...(a.movable ?? {}) },
            real_estate: { ...emptyAssets.real_estate, ...(a.real_estate ?? {}) },
            revolving: { ...emptyAssets.revolving, ...(a.revolving ?? {}) },
            income: { ...emptyAssets.income, ...(a.income ?? {}) },
          });
          const l = bs.liabilities ?? {};
          const fixedDefaults = JSON.parse(JSON.stringify(emptyLiabilities.fixed)) as Record<
            string,
            FixedDebtSlot
          >;
          if (l.fixed) {
            for (const key of Object.keys(fixedDefaults)) {
              if (l.fixed[key]) fixedDefaults[key] = { ...fixedDefaults[key], ...l.fixed[key] };
            }
          }
          setLiabilities({
            fixed: fixedDefaults,
            general: { ...emptyLiabilities.general, ...(l.general ?? {}) },
          } as BalanceSheetLiabilities);
        }
        setLoading(false);
      })
      .catch(() => {
        setError('無法載入資產負債表。');
        setLoading(false);
      });
  }, [id]);

  const setAssetField = useCallback((section: string, field: string, val: number) => {
    setAssets((prev) => ({
      ...prev,
      [section]: {
        ...(prev as unknown as Record<string, Record<string, number>>)[section],
        [field]: val,
      },
    }));
  }, []);

  const setDebtField = useCallback((key: string, field: string, val: number) => {
    setLiabilities((prev) => ({
      ...prev,
      fixed: {
        ...prev.fixed,
        [key]: { ...(prev.fixed as Record<string, FixedDebtSlot>)[key], [field]: val },
      },
    }));
  }, []);

  const setGeneralField = useCallback((field: string, val: number) => {
    setLiabilities((prev) => ({
      ...prev,
      general: { ...prev.general, [field]: val },
    }));
  }, []);

  const sumNum = (obj: Record<string, unknown> | undefined) =>
    obj
      ? Object.values(obj).reduce(
          (s: number, v) => s + (typeof v === 'number' ? v || 0 : 0),
          0,
        )
      : 0;

  const totalAssetsValue =
    sumNum(assets.cash) +
    sumNum(assets.investment) +
    sumNum(assets.movable) +
    sumNum(assets.real_estate) +
    sumNum(assets.revolving);
  const monthlyIncome = sumNum(assets.income);

  const fixedSlots = Object.values(liabilities.fixed) as FixedDebtSlot[];
  const totalDebtBalance = fixedSlots.reduce((s, d) => s + (d.balance || 0), 0);
  const totalFixedMonthly = fixedSlots.reduce((s, d) => s + (d.monthly_payment || 0), 0);
  const totalGeneralMonthly = sumNum(liabilities.general);
  const monthlyExpense = totalFixedMonthly + totalGeneralMonthly;
  const monthlyBalance = monthlyIncome - monthlyExpense;
  const netWorth = totalAssetsValue - totalDebtBalance;

  const handleSave = async () => {
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await api.post(`/api/clients/${id}/balance-sheet`, { assets, liabilities });
      setSaved(true);
      setTimeout(() => setSaved(false), 3000);
    } catch (err) {
      setError(err instanceof ApiError ? err.message : '儲存失敗，請確認資料庫連線正常。');
    } finally {
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
          { label: '資產負債' },
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
              onClick={handleSave}
              disabled={saving}
              className="btn-primary inline-flex shrink-0 items-center gap-2 rounded-lg px-4 py-2 text-[14px] disabled:opacity-50"
            >
              <Save className="h-4 w-4" strokeWidth={2} />
              {saving ? '儲存中…' : '儲存'}
            </button>
          </div>
        </div>
      </div>

      <main className="mx-auto max-w-[1200px] px-6 py-10">
        <div
          className="mb-8 border-l-4 pl-4"
          style={{ borderColor: 'var(--accent-primary)' }}
        >
          <h1 className="text-section-title">資產負債表</h1>
          <p className="mt-2 text-section-sub">
            填寫客戶目前資產、月收入、固定 / 一般支出與負債餘額。
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
          <>
            {/* summary strip */}
            <section className="mb-8 grid grid-cols-2 gap-3 md:grid-cols-3 lg:grid-cols-6">
              <Hero label="資產總計" value={totalAssetsValue} tone="pos" />
              <Hero label="負債總計" value={totalDebtBalance} tone="neg" />
              <Hero label="月收入總計" value={monthlyIncome} tone="pos" />
              <Hero label="月支出總計" value={monthlyExpense} tone="neg" />
              <Hero
                label="淨資產狀況"
                value={netWorth}
                tone={netWorth >= 0 ? 'pos' : 'neg'}
              />
              <Hero
                label="每月收支"
                value={monthlyBalance}
                tone={monthlyBalance >= 0 ? 'pos' : 'neg'}
              />
            </section>

            <div className="grid grid-cols-1 gap-6 xl:grid-cols-2">
              {/* Assets column */}
              <section className="rounded-xl border border-neutral-200 bg-white p-6">
                <SectionLabel num="A">資產</SectionLabel>
                <p className="mb-5 text-[12.5px] text-neutral-500">
                  可動用資產與收入來源
                </p>

                <div className="space-y-6">
                  {ASSET_SECTIONS.map((section) => (
                    <div key={section.key}>
                      <h3 className="mb-2 border-b border-neutral-100 pb-1 font-serif text-[15px] text-neutral-900">
                        {section.title}
                      </h3>
                      <div className="space-y-1">
                        {section.fields.map(([field, label]) => {
                          const val =
                            ((assets as unknown as Record<string, Record<string, number>>)[
                              section.key
                            ] ?? {})[field] || 0;
                          return (
                            <AmountRow
                              key={field}
                              label={label}
                              value={val}
                              onChange={(v) => setAssetField(section.key, field, v)}
                            />
                          );
                        })}
                      </div>
                      <div className="mt-1 flex justify-end font-mono text-[11px] text-neutral-500">
                        {section.key === 'income' ? '月收入合計' : '小計'}：
                        <span className="ml-1 tabular-nums text-neutral-900">
                          {formatTwd(
                            sumNum(
                              (assets as unknown as Record<string, Record<string, number>>)[
                                section.key
                              ],
                            ),
                          )}
                        </span>
                      </div>
                    </div>
                  ))}

                  <div className="flex items-center justify-between border-t border-neutral-200 pt-4">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                      資產總計
                    </span>
                    <span
                      className="font-serif tabular-nums text-neutral-900"
                      style={{ fontSize: 22, letterSpacing: '-0.01em' }}
                    >
                      {formatTwd(totalAssetsValue)}
                    </span>
                  </div>
                </div>
              </section>

              {/* Liabilities column */}
              <section className="rounded-xl border border-neutral-200 bg-white p-6">
                <SectionLabel num="L">負債</SectionLabel>
                <p className="mb-5 text-[12.5px] text-neutral-500">
                  固定負債與一般支出
                </p>

                {/* fixed debts table */}
                <div>
                  <h3 className="mb-2 border-b border-neutral-100 pb-1 font-serif text-[15px] text-neutral-900">
                    固定支出
                  </h3>
                  <p className="mb-2 text-[11.5px] text-neutral-500">
                    若同類型有多筆，請加總後填入。
                  </p>
                  <div className="overflow-x-auto">
                    <table className="w-full min-w-[520px] text-sm">
                      <thead>
                        <tr className="border-b border-neutral-200 text-[11px] uppercase tracking-wider text-neutral-500">
                          <th className="py-2 pl-1 text-left font-medium">名稱</th>
                          <th className="w-28 py-2 text-right font-medium">餘額</th>
                          <th className="w-24 py-2 text-right font-medium">月付金</th>
                          <th className="w-20 py-2 text-right font-medium">利率%</th>
                        </tr>
                      </thead>
                      <tbody>
                        {DEBT_KEYS.map(([key, label]) => {
                          const slot: FixedDebtSlot =
                            (liabilities.fixed as Record<string, FixedDebtSlot>)[key] || ES;
                          const inputCls =
                            'w-full rounded-md border border-neutral-200 bg-white px-1.5 py-1 text-right text-[12px] tabular-nums text-neutral-900 placeholder:text-neutral-300 focus:border-neutral-900 focus:outline-none';
                          return (
                            <tr
                              key={key}
                              className="border-b border-neutral-100 last:border-b-0"
                            >
                              <td className="py-1 pl-1 text-[12.5px] text-neutral-700 whitespace-nowrap">
                                {label}
                              </td>
                              <td className="py-1 px-0.5">
                                <input
                                  type="number"
                                  value={slot.balance || ''}
                                  onChange={(e) =>
                                    setDebtField(key, 'balance', Number(e.target.value) || 0)
                                  }
                                  className={inputCls}
                                  min={0}
                                  placeholder="0"
                                />
                              </td>
                              <td className="py-1 px-0.5">
                                <input
                                  type="number"
                                  value={slot.monthly_payment || ''}
                                  onChange={(e) =>
                                    setDebtField(
                                      key,
                                      'monthly_payment',
                                      Number(e.target.value) || 0,
                                    )
                                  }
                                  className={inputCls}
                                  min={0}
                                  placeholder="0"
                                />
                              </td>
                              <td className="py-1 px-0.5">
                                <input
                                  type="number"
                                  value={slot.rate || ''}
                                  onChange={(e) =>
                                    setDebtField(key, 'rate', Number(e.target.value) || 0)
                                  }
                                  className={inputCls}
                                  min={0}
                                  step={0.01}
                                  placeholder="0"
                                />
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                      <tfoot>
                        <tr className="border-t border-neutral-200 font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                          <td className="py-2 pl-1">合計</td>
                          <td className="py-2 pr-1 text-right tabular-nums text-neutral-900">
                            {formatTwd(totalDebtBalance)}
                          </td>
                          <td className="py-2 pr-1 text-right tabular-nums text-neutral-900">
                            {formatTwd(totalFixedMonthly)}
                          </td>
                          <td />
                        </tr>
                      </tfoot>
                    </table>
                  </div>
                </div>

                {/* general monthly */}
                <div className="mt-6">
                  <h3 className="mb-2 border-b border-neutral-100 pb-1 font-serif text-[15px] text-neutral-900">
                    一般支出（月）
                  </h3>
                  <div className="space-y-1">
                    {GENERAL_FIELDS.map(([field, label]) => {
                      const val =
                        (liabilities.general as unknown as Record<string, number>)[field] || 0;
                      return (
                        <AmountRow
                          key={field}
                          label={label}
                          value={val}
                          onChange={(v) => setGeneralField(field, v)}
                        />
                      );
                    })}
                  </div>
                  <div className="mt-1 flex justify-end font-mono text-[11px] text-neutral-500">
                    一般支出合計：
                    <span className="ml-1 tabular-nums text-neutral-900">
                      {formatTwd(totalGeneralMonthly)}
                    </span>
                  </div>
                </div>

                <div className="mt-6 space-y-2 border-t border-neutral-200 pt-4">
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                      負債總計
                    </span>
                    <span
                      className="font-serif tabular-nums text-neutral-900"
                      style={{ fontSize: 22, letterSpacing: '-0.01em' }}
                    >
                      {formatTwd(totalDebtBalance)}
                    </span>
                  </div>
                  <div className="flex items-center justify-between">
                    <span className="font-mono text-[11px] uppercase tracking-wider text-neutral-500">
                      月支出總計
                    </span>
                    <span
                      className="font-serif tabular-nums text-neutral-900"
                      style={{ fontSize: 22, letterSpacing: '-0.01em' }}
                    >
                      {formatTwd(monthlyExpense)}
                    </span>
                  </div>
                </div>
              </section>
            </div>

            <div className="mt-8 flex flex-wrap items-center justify-between gap-3 border-t border-neutral-200 pt-6">
              <Link
                to={`/clients/${clientId}`}
                className="text-[13px] text-neutral-500 hover:text-neutral-900"
              >
                ← 返回基本資料
              </Link>
              <div className="flex items-center gap-2">
                <button
                  type="button"
                  onClick={handleSave}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg border border-neutral-300 bg-white px-4 py-2 text-[13px] font-medium text-neutral-800 transition-colors hover:border-neutral-400 disabled:opacity-50"
                >
                  <Save className="h-3.5 w-3.5" strokeWidth={2} />
                  {saving ? '儲存中…' : '儲存'}
                </button>
                <button
                  type="button"
                  onClick={async () => {
                    await handleSave();
                    if (!error) {
                      window.location.href = `/clients/${clientId}/questionnaire`;
                    }
                  }}
                  disabled={saving}
                  className="inline-flex items-center gap-2 rounded-lg bg-neutral-900 px-5 py-2.5 text-[13px] font-medium text-white transition-colors hover:bg-neutral-800 disabled:opacity-50"
                >
                  儲存並前往退休問卷
                  <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                </button>
              </div>
            </div>
          </>
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
