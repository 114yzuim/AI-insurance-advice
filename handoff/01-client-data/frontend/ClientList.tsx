import { useEffect, useMemo, useState } from 'react';
import { Link, useNavigate } from 'react-router-dom';
import {
  Plus,
  Search,
  Edit3,
  ArrowRight,
  Trash2,
  Users,
  ChevronRight,
  Clock,
  Command,
  TrendingUp,
  Shield,
  HeartPulse,
} from 'lucide-react';
import type { Client, ModuleCode } from '../../shared/types';
import { STATUS_LABEL } from '../lib/labels';
import { api, ApiError } from '../lib/api';
import TopBar from '../components/TopBar';

/* =========================================================================
   ClientList.tsx — 客戶名冊（Notion / Linear 風）
   與 Home / Simulator 一致的 self-chromed 版型。
   ========================================================================= */

function SectionLabel({ num, children }: { num: string; children: React.ReactNode }) {
  return (
    <div className="flex items-baseline gap-3">
      <span className="font-mono text-[11px] tracking-[0.18em] text-neutral-400">{num}</span>
      <span className="font-mono text-[11px] uppercase tracking-[0.18em] text-neutral-500">
        {children}
      </span>
    </div>
  );
}

function ModuleBadge({ id }: { id: ModuleCode }) {
  return (
    <span className="inline-flex h-5 min-w-[20px] items-center justify-center rounded border border-neutral-200 bg-white px-1 font-mono text-[11px] font-medium text-neutral-600">
      {id}
    </span>
  );
}

function StatusPill({ status }: { status?: string }) {
  const key = status ?? 'new';
  return (
    <span className="inline-flex items-center rounded border border-neutral-200 bg-neutral-50 px-1.5 py-0.5 font-mono text-[10.5px] text-neutral-600">
      {STATUS_LABEL[key] || '新建'}
    </span>
  );
}

function RiskTag({ risk }: { risk?: string | null }) {
  const map: Record<string, string> = {
    conservative: '跌幅低',
    moderate: '跌幅中',
    aggressive: '跌幅高',
    Conservative: '跌幅低',
    Moderate: '跌幅中',
    Aggressive: '跌幅高',
    保守: '跌幅低',
    穩健: '跌幅中',
    積極: '跌幅高',
  };
  const label = map[risk ?? ''] ?? '—';
  return <span className="font-mono text-[11px] text-neutral-500">{label}</span>;
}

function relativeLabel(isoOrDate?: string | null): string {
  if (!isoOrDate) return '—';
  const t = new Date(isoOrDate).getTime();
  if (Number.isNaN(t)) return '—';
  const diffMs = Date.now() - t;
  const hour = 3600 * 1000;
  const day = 24 * hour;
  if (diffMs < hour) return '剛剛';
  if (diffMs < day) return `${Math.floor(diffMs / hour)} 小時前`;
  if (diffMs < 2 * day) return '昨天';
  if (diffMs < 7 * day) return `${Math.floor(diffMs / day)} 天前`;
  if (diffMs < 30 * day) return `${Math.floor(diffMs / day)} 天前`;
  return new Date(t).toISOString().slice(0, 10);
}

export default function ClientList() {
  const navigate = useNavigate();
  const [clients, setClients] = useState<Client[]>([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [search, setSearch] = useState('');

  useEffect(() => {
    let cancelled = false;
    setLoading(true);
    api
      .get<Client[]>('/api/clients')
      .then((data) => {
        if (cancelled) return;
        // newest first
        data.sort((a, b) => {
          const ta = new Date(a.updated_at ?? a.created_at ?? 0).getTime();
          const tb = new Date(b.updated_at ?? b.created_at ?? 0).getTime();
          return tb - ta;
        });
        setClients(data);
        setError(null);
      })
      .catch((err: ApiError | Error) => {
        if (cancelled) return;
        setError(err.message || '資料庫未連線，請確認 PostgreSQL 伺服器已啟動。');
      })
      .finally(() => {
        if (!cancelled) setLoading(false);
      });
    return () => {
      cancelled = true;
    };
  }, []);

  const handleDelete = async (id: number, name: string) => {
    if (!confirm(`確定要刪除客戶「${name}」嗎？此操作無法復原。`)) return;
    try {
      await api.del(`/api/clients/${id}`);
      setClients((prev) => prev.filter((c) => c.id !== id));
    } catch {
      alert('刪除失敗');
    }
  };

  const filtered = useMemo(
    () =>
      clients.filter(
        (c) =>
          !search ||
          c.name.includes(search) ||
          (c.email ?? '').includes(search) ||
          (c.phone ?? '').includes(search),
      ),
    [clients, search],
  );

  const runSimulator = (c: Client) => {
    if (c.id == null) return;
    const mods = (c.selected_modules?.length
      ? c.selected_modules
      : ['A']) as ModuleCode[];
    navigate(`/clients/${c.id}/simulator?modules=${mods.join(',')}`);
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
          { label: '客戶名冊' },
        ]}
      />

      {/* ---------------- page ---------------- */}
      <main className="mx-auto max-w-[1200px] px-6 py-10 md:py-12">
        <div className="mb-6 flex justify-end">
          <Link
            to="/clients/new"
            className="btn-primary inline-flex items-center gap-2 rounded-lg px-4 py-2 text-[14px]"
          >
            <Plus className="h-4 w-4" strokeWidth={2} />
            新增客戶
          </Link>
        </div>
        {/* hero — 暮霞風 */}
        <div
          className="mb-8 border-l-4 pl-4"
          style={{ borderColor: 'var(--accent-primary)' }}
        >
          <h1 className="text-section-title">客戶名冊</h1>
          <p className="mt-2 text-section-sub">
            共 {clients.length} 位客戶 · 點擊列表項進入對應工作流。
          </p>
        </div>

        {/* search */}
        <section className="mb-6">
          <SectionLabel num="01">搜尋 / 篩選</SectionLabel>
          <div className="mt-3 flex items-center gap-3 rounded-xl border border-neutral-200 bg-white px-4 py-3 transition-colors focus-within:border-neutral-400">
            <Search className="h-4 w-4 text-neutral-400" strokeWidth={1.75} />
            <input
              type="text"
              value={search}
              onChange={(e) => setSearch(e.target.value)}
              placeholder="輸入姓名 / Email / 電話…"
              className="flex-1 bg-transparent text-sm text-neutral-900 placeholder:text-neutral-400 focus:outline-none"
            />
            <span className="inline-flex items-center gap-1 rounded border border-neutral-200 bg-neutral-50 px-1.5 py-0.5 font-mono text-[10px] text-neutral-500">
              <Command className="h-3 w-3" strokeWidth={1.75} />K
            </span>
          </div>
        </section>

        {/* list */}
        <section className="mb-16">
          <div className="mb-3 flex items-baseline justify-between">
            <SectionLabel num="02">客戶列表</SectionLabel>
            <span className="font-mono text-[11px] text-neutral-400">
              {filtered.length} / {clients.length}
            </span>
          </div>

          {loading ? (
            <div className="rounded-xl border border-neutral-200 bg-white py-16 text-center text-sm text-neutral-400">
              載入中…
            </div>
          ) : error ? (
            <div className="rounded-xl border border-red-200 bg-red-50 px-4 py-4 text-[13px] text-red-800">
              {error}
            </div>
          ) : filtered.length === 0 ? (
            <div className="rounded-xl border border-dashed border-neutral-200 bg-white px-6 py-16 text-center">
              <div className="mx-auto mb-4 grid h-12 w-12 place-items-center rounded-full border border-neutral-200 bg-neutral-50">
                <Users className="h-5 w-5 text-neutral-500" strokeWidth={1.75} />
              </div>
              <h3 className="font-serif text-lg text-neutral-900">
                {search ? '沒有符合條件的客戶' : '尚無客戶資料'}
              </h3>
              <p className="mt-1 text-[13px] text-neutral-500">
                {search ? '嘗試不同的搜尋條件。' : '建立第一位客戶開始規劃。'}
              </p>
              {!search && (
                <Link
                  to="/clients/new"
                  className="mt-5 inline-flex items-center gap-2 rounded-lg bg-neutral-900 px-4 py-2 text-[13px] font-medium text-white transition-colors hover:bg-neutral-800"
                >
                  <Plus className="h-3.5 w-3.5" strokeWidth={2} />
                  新增第一位客戶
                </Link>
              )}
            </div>
          ) : (
            <ul className="overflow-hidden rounded-xl border border-neutral-200 bg-white">
              <li className="grid grid-cols-[1.6fr_0.6fr_0.8fr_0.8fr_0.9fr_0.9fr_auto] items-center gap-4 border-b border-neutral-200 bg-neutral-50/60 px-5 py-2.5 font-mono text-[10.5px] uppercase tracking-wider text-neutral-500">
                <span>姓名 / Email</span>
                <span>年齡</span>
                <span>退休</span>
                <span>跌幅承受</span>
                <span>模組</span>
                <span>進度 / 更新</span>
                <span className="text-right">操作</span>
              </li>

              {filtered.map((c) => {
                const mods = (c.selected_modules ?? ['A']) as ModuleCode[];
                return (
                  <li
                    key={c.id}
                    className="group grid grid-cols-[1.6fr_0.6fr_0.8fr_0.8fr_0.9fr_0.9fr_auto] items-center gap-4 border-b border-neutral-100 px-5 py-3 transition-colors last:border-b-0 hover:bg-neutral-50/80"
                  >
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <Link
                          to={`/clients/${c.id}`}
                          className="truncate text-[14px] font-medium text-neutral-900 hover:text-neutral-700 hover:underline underline-offset-2"
                        >
                          {c.name}
                        </Link>
                        {c.is_joint_plan && (
                          <span className="inline-flex items-center rounded border border-purple-200 bg-purple-50 px-1.5 py-0.5 font-mono text-[10px] font-medium text-purple-700">
                            聯合
                          </span>
                        )}
                      </div>
                      <div className="mt-0.5 truncate text-[11.5px] text-neutral-500">
                        {c.email || c.phone || '—'}
                      </div>
                    </div>

                    <div className="font-mono tabular-nums text-[13px] text-neutral-700">
                      {c.age}
                    </div>
                    <div className="font-mono tabular-nums text-[13px] text-neutral-700">
                      {c.target_retire_age ?? '—'}
                    </div>
                    <div>
                      <RiskTag risk={c.risk_tolerance} />
                    </div>

                    <div className="flex items-center gap-1">
                      {mods.map((m) => (
                        <span key={m} className="inline-flex items-center gap-1">
                          {m === 'A' && (
                            <TrendingUp className="h-3 w-3 text-neutral-400" strokeWidth={1.75} />
                          )}
                          {m === 'B' && (
                            <Shield className="h-3 w-3 text-neutral-400" strokeWidth={1.75} />
                          )}
                          {m === 'C' && (
                            <HeartPulse className="h-3 w-3 text-neutral-400" strokeWidth={1.75} />
                          )}
                          <ModuleBadge id={m} />
                        </span>
                      ))}
                    </div>

                    <div className="flex flex-col gap-0.5">
                      <StatusPill status={c.status} />
                      <span className="flex items-center gap-1 font-mono text-[10.5px] text-neutral-400">
                        <Clock className="h-3 w-3" strokeWidth={1.75} />
                        {relativeLabel(c.updated_at ?? c.created_at)}
                      </span>
                    </div>

                    <div className="flex items-center justify-end gap-1 opacity-0 transition-opacity group-hover:opacity-100">
                      <button
                        type="button"
                        onClick={() => runSimulator(c)}
                        className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-[11.5px] text-neutral-700 hover:bg-neutral-100"
                        title="開始推演"
                      >
                        <ArrowRight className="h-3.5 w-3.5" strokeWidth={2} />
                        推演
                      </button>
                      <Link
                        to={`/clients/${c.id}/basic-info`}
                        className="inline-flex items-center gap-1 rounded-md border border-transparent px-2 py-1 text-[11.5px] text-neutral-600 hover:bg-neutral-100"
                        title="編輯"
                      >
                        <Edit3 className="h-3.5 w-3.5" strokeWidth={2} />
                        編輯
                      </Link>
                      <button
                        type="button"
                        onClick={() => c.id != null && handleDelete(c.id, c.name)}
                        className="inline-flex items-center rounded-md border border-transparent px-1.5 py-1 text-neutral-400 hover:bg-red-50 hover:text-red-600"
                        title="刪除"
                      >
                        <Trash2 className="h-3.5 w-3.5" strokeWidth={1.75} />
                      </button>
                    </div>
                  </li>
                );
              })}
            </ul>
          )}
        </section>

        <footer className="flex flex-wrap items-center justify-between gap-3 border-t border-neutral-200 pt-6 font-mono text-[11px] text-neutral-400">
          <span>© 2026 退休規劃</span>
          <span>保經內部試算工具 · 非保險公司建議書</span>
        </footer>
      </main>
    </div>
  );
}
