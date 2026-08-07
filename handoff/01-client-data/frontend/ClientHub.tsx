import { useEffect, useMemo, useState } from 'react';
import { Link, useParams } from 'react-router-dom';
import {
  ArrowRight,
  ChevronDown,
  ChevronUp,
  ClipboardList,
  Pencil,
  UserRound,
  Wallet,
} from 'lucide-react';
import type { Client, ModuleCode, Questionnaire } from '../../shared/types';
import { api } from '../lib/api';
import { STATUS_LABEL } from '../lib/labels';
import { formatTwd } from '../lib/utils';
import TopBar from '../components/TopBar';

interface BalanceSheetSummary {
  total_assets?: number;
  total_liabilities?: number;
  net_worth?: number;
  monthly_income?: number;
  monthly_expense?: number;
  monthly_balance?: number;
}

type SectionKey = 'basic' | 'balance' | 'questionnaire';

const MODULE_LABEL: Record<ModuleCode, string> = {
  A: '投資',
  B: '保險',
  C: '失能長照',
};

function ModuleBadge({ id }: { id: ModuleCode }) {
  return (
    <span className="inline-flex items-center gap-1 rounded-md border border-neutral-200 bg-white px-2 py-1 text-[12px] font-medium text-neutral-700">
      <span className="font-mono">{id}</span>
      <span>{MODULE_LABEL[id]}</span>
    </span>
  );
}

function EmptyText({ children }: { children: React.ReactNode }) {
  return <span className="text-[13px] text-neutral-400">{children}</span>;
}

function InfoGrid({ children }: { children: React.ReactNode }) {
  return <dl className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">{children}</dl>;
}

function InfoItem({ label, value }: { label: string; value: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-neutral-200 bg-white px-3 py-3">
      <dt className="font-mono text-[10px] uppercase tracking-wider text-neutral-400">
        {label}
      </dt>
      <dd className="mt-1 text-[15px] font-medium text-neutral-900">{value}</dd>
    </div>
  );
}

function questionnaireTargetToTwd(value: unknown): number {
  const n = Number(value);
  if (!Number.isFinite(n) || n <= 0) return 0;
  return n > 10_000 ? n : n * 10_000;
}

function CollapsibleSection({
  icon: Icon,
  title,
  subtitle,
  open,
  onToggle,
  action,
  children,
}: {
  icon: typeof UserRound;
  title: string;
  subtitle: string;
  open: boolean;
  onToggle: () => void;
  action: React.ReactNode;
  children: React.ReactNode;
}) {
  return (
    <section className="overflow-hidden rounded-xl border border-neutral-200 bg-white">
      <button
        type="button"
        onClick={onToggle}
        className="flex w-full items-center gap-4 px-5 py-4 text-left transition-colors hover:bg-neutral-50"
      >
        <span
          className="grid h-10 w-10 shrink-0 place-items-center rounded-lg"
          style={{ background: 'var(--surface-elevated)', color: 'var(--accent-primary)' }}
        >
          <Icon className="h-5 w-5" strokeWidth={2} />
        </span>
        <span className="min-w-0 flex-1">
          <span className="block text-[17px] font-semibold text-neutral-900">{title}</span>
          <span className="mt-0.5 block text-[13px] text-neutral-500">{subtitle}</span>
        </span>
        {open ? (
          <ChevronUp className="h-5 w-5 shrink-0 text-neutral-400" strokeWidth={2} />
        ) : (
          <ChevronDown className="h-5 w-5 shrink-0 text-neutral-400" strokeWidth={2} />
        )}
      </button>
      {open && (
        <div className="border-t border-neutral-100 bg-neutral-50/50 px-5 py-5">
          {children}
          <div className="mt-5 flex justify-end">{action}</div>
        </div>
      )}
    </section>
  );
}

export default function ClientHub() {
  const { id } = useParams<{ id: string }>();
  const clientId = id ?? '';
  const [client, setClient] = useState<Client | null>(null);
  const [balanceSheet, setBalanceSheet] = useState<BalanceSheetSummary | null>(null);
  const [questionnaire, setQuestionnaire] = useState<Questionnaire | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [open, setOpen] = useState<Record<SectionKey, boolean>>({
    basic: true,
    balance: false,
    questionnaire: false,
  });

  useEffect(() => {
    if (!clientId) return;
    let cancelled = false;
    setLoading(true);
    setError(null);
    Promise.all([
      api.get<Client>(`/api/clients/${clientId}`),
      api
        .get<BalanceSheetSummary | null>(`/api/clients/${clientId}/balance-sheet`)
        .catch(() => null),
      api.get<Questionnaire | null>(`/api/questionnaires/${clientId}`).catch(() => null),
    ])
      .then(([clientData, balanceData, questionnaireData]) => {
        if (cancelled) return;
        setClient(clientData);
        setBalanceSheet(balanceData);
        setQuestionnaire(questionnaireData);
      })
      .catch((err) => {
        if (cancelled) return;
        setError(err instanceof Error ? err.message : '無法載入客戶資料。');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, [clientId]);

  const modules = useMemo<ModuleCode[]>(
    () => ((client?.selected_modules?.length ? client.selected_modules : ['A']) as ModuleCode[]),
    [client?.selected_modules],
  );

  const completion = useMemo(() => {
    const basicDone = Boolean(client?.age && client?.target_retire_age);
    const balanceDone = Boolean(balanceSheet);
    const questionnaireDone = client?.status === 'questionnaire_done' || Boolean(questionnaire);
    const done = [basicDone, balanceDone, questionnaireDone].filter(Boolean).length;
    return { basicDone, balanceDone, questionnaireDone, done };
  }, [balanceSheet, client?.age, client?.status, client?.target_retire_age, questionnaire]);

  const moduleQuery = modules.join(',');
  const statusLabel = STATUS_LABEL[client?.status ?? 'new'] ?? '待填問卷';

  const toggle = (key: SectionKey) => setOpen((prev) => ({ ...prev, [key]: !prev[key] }));

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
          { label: client?.name || '規劃資料' },
        ]}
        modules={modules}
      />

      <main className="mx-auto max-w-[1080px] px-6 py-10 md:py-12">
        {loading ? (
          <div className="rounded-xl border border-neutral-200 bg-white py-16 text-center text-sm text-neutral-400">
            載入中…
          </div>
        ) : error || !client ? (
          <div className="rounded-xl border border-red-200 bg-red-50 px-5 py-4 text-[14px] text-red-800">
            {error || '找不到客戶。'}
          </div>
        ) : (
          <>
            <div className="mb-7 flex flex-col gap-4 border-l-4 pl-5 md:flex-row md:items-end md:justify-between" style={{ borderColor: 'var(--accent-primary)' }}>
              <div>
                <div className="mb-2 flex flex-wrap items-center gap-2">
                  {client.is_demo && (
                    <span className="rounded border border-amber-200 bg-amber-50 px-2 py-0.5 text-[12px] font-medium text-amber-800">
                      Demo
                    </span>
                  )}
                  <span className="rounded border border-neutral-200 bg-white px-2 py-0.5 text-[12px] text-neutral-600">
                    {statusLabel}
                  </span>
                  <span className="rounded border border-neutral-200 bg-white px-2 py-0.5 text-[12px] text-neutral-600">
                    完整度 {completion.done}/3
                  </span>
                </div>
                <h1 className="text-section-title">{client.name} · 規劃資料</h1>
                <p className="mt-2 text-section-sub">
                  先確認客戶資料是否足夠，再進入退休規劃。此頁只做摘要，編輯仍回專屬頁。
                </p>
              </div>
              <Link
                to={`/clients/${clientId}/studio`}
                className="btn-primary inline-flex shrink-0 items-center justify-center gap-2 rounded-lg px-5 py-3 text-[15px]"
              >
                進入退休規劃
                <ArrowRight className="h-4 w-4" strokeWidth={2} />
              </Link>
            </div>

            <div className="space-y-4">
              <CollapsibleSection
                icon={UserRound}
                title="基本資料"
                subtitle={completion.basicDone ? '已可進入規劃' : '仍需補齊年齡與退休時程'}
                open={open.basic}
                onToggle={() => toggle('basic')}
                action={
                  <Link
                    to={`/clients/${clientId}/basic-info`}
                    className="inline-flex items-center gap-2 rounded-lg border border-neutral-300 bg-white px-4 py-2 text-[13px] font-medium text-neutral-800 hover:border-neutral-400"
                  >
                    <Pencil className="h-3.5 w-3.5" strokeWidth={2} />
                    編輯基本資料
                  </Link>
                }
              >
                <InfoGrid>
                  <InfoItem label="年齡" value={client.age ? `${client.age} 歲` : <EmptyText>尚未填寫</EmptyText>} />
                  <InfoItem label="退休年齡" value={client.target_retire_age ? `${client.target_retire_age} 歲` : <EmptyText>尚未填寫</EmptyText>} />
                  <InfoItem label="月可存" value={formatTwd(client.monthly_investable ?? 0)} />
                  <InfoItem label="目標月領" value={formatTwd(client.target_retire_monthly_expense ?? 0)} />
                </InfoGrid>
                <div className="mt-4 flex flex-wrap items-center gap-2">
                  <span className="text-[13px] text-neutral-500">目前模組</span>
                  {modules.map((module) => (
                    <ModuleBadge key={module} id={module} />
                  ))}
                </div>
              </CollapsibleSection>

              <CollapsibleSection
                icon={Wallet}
                title="資產負債"
                subtitle={completion.balanceDone ? '已有資產負債摘要' : '尚未填寫資產負債表'}
                open={open.balance}
                onToggle={() => toggle('balance')}
                action={
                  <Link
                    to={`/clients/${clientId}/balance-sheet`}
                    className="inline-flex items-center gap-2 rounded-lg border border-neutral-300 bg-white px-4 py-2 text-[13px] font-medium text-neutral-800 hover:border-neutral-400"
                  >
                    <Pencil className="h-3.5 w-3.5" strokeWidth={2} />
                    編輯資產負債
                  </Link>
                }
              >
                {balanceSheet ? (
                  <InfoGrid>
                    <InfoItem label="總資產" value={formatTwd(balanceSheet.total_assets ?? client.current_assets ?? 0)} />
                    <InfoItem label="總負債" value={formatTwd(balanceSheet.total_liabilities ?? client.current_liabilities ?? 0)} />
                    <InfoItem label="淨值" value={formatTwd(balanceSheet.net_worth ?? 0)} />
                    <InfoItem label="每月收支" value={formatTwd(balanceSheet.monthly_balance ?? 0)} />
                  </InfoGrid>
                ) : (
                  <div className="rounded-lg border border-dashed border-neutral-200 bg-white px-4 py-6 text-[14px] text-neutral-500">
                    尚未填寫資產負債表。可直接進入退休規劃；若要更貼近客戶狀況，建議先補這段。
                  </div>
                )}
              </CollapsibleSection>

              <CollapsibleSection
                icon={ClipboardList}
                title="退休問卷"
                subtitle={completion.questionnaireDone ? '已有問卷資料' : '尚未完成退休問卷'}
                open={open.questionnaire}
                onToggle={() => toggle('questionnaire')}
                action={
                  <Link
                    to={`/clients/${clientId}/questionnaire`}
                    className="inline-flex items-center gap-2 rounded-lg border border-neutral-300 bg-white px-4 py-2 text-[13px] font-medium text-neutral-800 hover:border-neutral-400"
                  >
                    <Pencil className="h-3.5 w-3.5" strokeWidth={2} />
                    編輯問卷
                  </Link>
                }
              >
                {questionnaire ? (
                  <div className="space-y-4">
                    <InfoGrid>
                      <InfoItem label="退休金目標" value={formatTwd(questionnaireTargetToTwd(questionnaire.retire_target_amount))} />
                      <InfoItem label="退休月生活費" value={formatTwd(questionnaire.retire_monthly_living ?? 0)} />
                      <InfoItem label="月投入預算" value={formatTwd(questionnaire.monthly_investable_budget ?? 0)} />
                      <InfoItem label="健康狀況" value={questionnaire.health_status || <EmptyText>尚未填寫</EmptyText>} />
                    </InfoGrid>
                    <div className="grid grid-cols-1 gap-3 md:grid-cols-2">
                      <div className="rounded-lg border border-neutral-200 bg-white px-3 py-3">
                        <div className="font-mono text-[10px] uppercase tracking-wider text-neutral-400">
                          關注議題
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {(questionnaire.interested_topics ?? []).length ? (
                            questionnaire.interested_topics.map((topic) => (
                              <span key={topic} className="rounded border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[12px] text-neutral-700">
                                {topic}
                              </span>
                            ))
                          ) : (
                            <EmptyText>尚未填寫</EmptyText>
                          )}
                        </div>
                      </div>
                      <div className="rounded-lg border border-neutral-200 bg-white px-3 py-3">
                        <div className="font-mono text-[10px] uppercase tracking-wider text-neutral-400">
                          風險因素
                        </div>
                        <div className="mt-2 flex flex-wrap gap-1.5">
                          {(questionnaire.risk_factors ?? []).length ? (
                            questionnaire.risk_factors.map((risk) => (
                              <span key={risk} className="rounded border border-neutral-200 bg-neutral-50 px-2 py-0.5 text-[12px] text-neutral-700">
                                {risk}
                              </span>
                            ))
                          ) : (
                            <EmptyText>尚未填寫</EmptyText>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                ) : (
                  <div className="rounded-lg border border-dashed border-neutral-200 bg-white px-4 py-6 text-[14px] text-neutral-500">
                    尚未填寫退休問卷。完成後可把月投入與退休月生活費同步回推演預設值。
                  </div>
                )}
              </CollapsibleSection>
            </div>

            <footer className="mt-16 flex flex-wrap items-center justify-between gap-3 border-t border-neutral-200 pt-6 font-mono text-[11px] text-neutral-400">
              <span>© 2026 退休規劃</span>
              <span>保經內部試算工具 · 非保險公司建議書</span>
            </footer>
          </>
        )}
      </main>
    </div>
  );
}
