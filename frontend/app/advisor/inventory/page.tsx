import Link from "next/link";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

type CompanyStatus = {
  slug: string;
  company: string;
  company_name: string;
  type: "life" | "property" | "reinsurance";
  products: number;
  documents: number;
  downloaded_documents: number;
  parsed_documents: number;
  pending_documents: number;
  browser_required_documents: number;
  chunks: number;
  inventory_status: "ready" | "partial" | "browser_required" | "missing";
  action: string;
  updated_at: string | null;
};

type TypeSummary = {
  type: string;
  companies: number;
  covered_companies: number;
  products: number;
  documents: number;
  parsed_documents: number;
};

type RemainingGap = {
  company: string;
  reason: string;
  next_step: string;
};

type InventorySummary = {
  companies: number;
  products: number;
  documents: number;
  downloaded_documents: number;
  parsed_documents: number;
  chunks: number;
  company_status: CompanyStatus[];
  by_type: TypeSummary[];
  remaining_gaps: RemainingGap[];
};

async function getInventorySummary(): Promise<InventorySummary | null> {
  try {
    const res = await fetch(`${BACKEND}/products/inventory-summary`, { cache: "no-store" });
    if (!res.ok) return null;
    return res.json();
  } catch {
    return null;
  }
}

function formatNumber(value: number | null | undefined) {
  return (value ?? 0).toLocaleString("zh-TW");
}

function percent(part: number, total: number) {
  if (!total) return 0;
  return Math.round((part / total) * 100);
}

function typeLabel(type: string) {
  if (type === "life") return "壽險";
  if (type === "property") return "產險";
  if (type === "reinsurance") return "再保";
  return type;
}

function statusStyle(status: CompanyStatus["inventory_status"]) {
  switch (status) {
    case "ready":
      return "bg-emerald-50 text-emerald-700 ring-emerald-100";
    case "partial":
      return "bg-amber-50 text-amber-700 ring-amber-100";
    case "browser_required":
      return "bg-sky-50 text-sky-700 ring-sky-100";
    default:
      return "bg-slate-100 text-slate-600 ring-slate-200";
  }
}

function statusLabel(status: CompanyStatus["inventory_status"]) {
  switch (status) {
    case "ready":
      return "可用";
    case "partial":
      return "部分可用";
    case "browser_required":
      return "需瀏覽器";
    default:
      return "待補";
  }
}

export default async function AdvisorInventoryPage() {
  const summary = await getInventorySummary();

  if (!summary) {
    return (
      <main className="mx-auto flex w-full max-w-6xl flex-1 flex-col px-4 py-8 md:px-6">
        <div className="rounded-lg border border-rose-200 bg-rose-50 p-5 text-sm text-rose-700">
          目前無法讀取產品資料庫，請確認後端服務是否啟動。
        </div>
      </main>
    );
  }

  const life = summary.by_type.find((item) => item.type === "life");
  const property = summary.by_type.find((item) => item.type === "property");
  const readyCompanies = summary.company_status.filter((item) => item.inventory_status === "ready").length;
  const missingCompanies = summary.company_status.filter((item) => item.inventory_status === "missing").length;
  const sortedCompanies = [...summary.company_status].sort((a, b) => {
    if (a.type !== b.type) return a.type.localeCompare(b.type);
    if (a.inventory_status === "missing" && b.inventory_status !== "missing") return 1;
    if (a.inventory_status !== "missing" && b.inventory_status === "missing") return -1;
    return b.products - a.products || a.company.localeCompare(b.company, "zh-Hant");
  });

  return (
    <main className="min-h-full bg-slate-50">
      <div className="mx-auto w-full max-w-7xl px-4 py-8 md:px-6">
        <div className="mb-6 flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-bold text-amber-700">顧問工作台</p>
            <h1 className="mt-2 text-3xl font-bold text-slate-950">產品資料庫</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
              管理 AI 底層使用的保險公司、商品、PDF 文件與條款解析狀態。客戶端不直接瀏覽完整資料庫，AI 顧問與理賠中心會在需要時讀取這些資料。
            </p>
          </div>
          <Link
            href="/products"
            className="inline-flex h-10 items-center justify-center rounded-lg border border-slate-200 bg-white px-4 text-sm font-bold text-slate-600 shadow-sm transition hover:border-amber-300 hover:text-amber-700"
          >
            查看商品清單
          </Link>
        </div>

        <section className="mb-5 grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
          <Metric label="保險公司" value={formatNumber(summary.companies)} />
          <Metric label="商品數" value={formatNumber(summary.products)} tone="text-amber-700" />
          <Metric label="文件數" value={formatNumber(summary.documents)} tone="text-sky-700" />
          <Metric label="已下載" value={formatNumber(summary.downloaded_documents)} tone="text-teal-700" />
          <Metric label="已解析" value={formatNumber(summary.parsed_documents)} tone="text-emerald-700" />
          <Metric label="條款 chunks" value={formatNumber(summary.chunks)} tone="text-violet-700" />
        </section>

        <section className="mb-6 grid gap-4 lg:grid-cols-[1fr_1fr_1.2fr]">
          <CoverageBlock
            title="壽險覆蓋"
            covered={life?.covered_companies ?? 0}
            total={life?.companies ?? 0}
            products={life?.products ?? 0}
            documents={life?.documents ?? 0}
          />
          <CoverageBlock
            title="產險覆蓋"
            covered={property?.covered_companies ?? 0}
            total={property?.companies ?? 0}
            products={property?.products ?? 0}
            documents={property?.documents ?? 0}
          />
          <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
            <p className="text-sm font-bold text-slate-700">資料狀態</p>
            <div className="mt-4 grid grid-cols-2 gap-3">
              <MiniStat label="可直接使用" value={`${readyCompanies} 家`} />
              <MiniStat label="仍待補齊" value={`${missingCompanies} 家`} />
            </div>
            <p className="mt-4 text-sm leading-6 text-slate-500">
              目前優先把人壽公司補到可回測，剩餘缺口多屬於瀏覽器驗證、API 參數或資料歸屬確認。
            </p>
          </div>
        </section>

        <section className="mb-6 rounded-lg border border-slate-200 bg-white shadow-sm">
          <div className="flex flex-col gap-2 border-b border-slate-200 px-4 py-4 md:flex-row md:items-center md:justify-between">
            <div>
              <h2 className="text-base font-bold text-slate-900">公司覆蓋明細</h2>
              <p className="mt-1 text-sm text-slate-500">依公司檢查商品、文件、下載、解析與可用狀態。</p>
            </div>
            <span className="text-sm font-bold text-slate-400">{summary.company_status.length} 家公司</span>
          </div>
          <div className="overflow-x-auto">
            <table className="w-full min-w-[980px] table-fixed text-sm">
              <thead className="bg-slate-50 text-slate-500">
                <tr>
                  <th className="w-[180px] px-4 py-3 text-left font-bold">公司</th>
                  <th className="w-[80px] px-4 py-3 text-left font-bold">類型</th>
                  <th className="w-[90px] px-4 py-3 text-right font-bold">商品</th>
                  <th className="w-[90px] px-4 py-3 text-right font-bold">文件</th>
                  <th className="w-[90px] px-4 py-3 text-right font-bold">已下載</th>
                  <th className="w-[90px] px-4 py-3 text-right font-bold">已解析</th>
                  <th className="w-[100px] px-4 py-3 text-right font-bold">需瀏覽器</th>
                  <th className="w-[120px] px-4 py-3 text-right font-bold">chunks</th>
                  <th className="w-[120px] px-4 py-3 text-left font-bold">狀態</th>
                  <th className="w-[170px] px-4 py-3 text-left font-bold">下一步</th>
                </tr>
              </thead>
              <tbody className="divide-y divide-slate-100">
                {sortedCompanies.map((company) => (
                  <tr key={company.slug} className="hover:bg-slate-50">
                    <td className="px-4 py-3 font-bold text-slate-900">{company.company}</td>
                    <td className="px-4 py-3 text-slate-500">{typeLabel(company.type)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatNumber(company.products)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatNumber(company.documents)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatNumber(company.downloaded_documents)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatNumber(company.parsed_documents)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatNumber(company.browser_required_documents)}</td>
                    <td className="px-4 py-3 text-right tabular-nums text-slate-700">{formatNumber(company.chunks)}</td>
                    <td className="px-4 py-3">
                      <span className={`inline-flex rounded-md px-2 py-1 text-xs font-bold ring-1 ${statusStyle(company.inventory_status)}`}>
                        {statusLabel(company.inventory_status)}
                      </span>
                    </td>
                    <td className="px-4 py-3 text-slate-500">{company.action}</td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </section>

        <section className="grid gap-3 lg:grid-cols-2">
          {summary.remaining_gaps.map((gap) => (
            <div key={gap.company} className="rounded-lg border border-amber-200 bg-amber-50 p-4">
              <h3 className="text-sm font-bold text-amber-900">{gap.company}</h3>
              <p className="mt-2 text-sm leading-6 text-amber-800">{gap.reason}</p>
              <p className="mt-3 text-sm font-bold text-amber-900">下一步：{gap.next_step}</p>
            </div>
          ))}
        </section>
      </div>
    </main>
  );
}

function Metric({ label, value, tone = "text-slate-950" }: { label: string; value: string; tone?: string }) {
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <p className="text-sm font-medium text-slate-500">{label}</p>
      <p className={`mt-2 text-2xl font-bold tabular-nums ${tone}`}>{value}</p>
    </div>
  );
}

function MiniStat({ label, value }: { label: string; value: string }) {
  return (
    <div className="rounded-lg bg-slate-50 p-3">
      <p className="text-xs font-bold text-slate-400">{label}</p>
      <p className="mt-1 text-lg font-bold text-slate-900">{value}</p>
    </div>
  );
}

function CoverageBlock({
  title,
  covered,
  total,
  products,
  documents,
}: {
  title: string;
  covered: number;
  total: number;
  products: number;
  documents: number;
}) {
  const coverage = percent(covered, total);
  return (
    <div className="rounded-lg border border-slate-200 bg-white p-4 shadow-sm">
      <div className="flex items-start justify-between gap-4">
        <div>
          <p className="text-sm font-bold text-slate-700">{title}</p>
          <p className="mt-2 text-2xl font-bold text-slate-950">
            {covered} / {total}
          </p>
        </div>
        <span className="rounded-md bg-slate-100 px-2 py-1 text-sm font-bold text-slate-600">{coverage}%</span>
      </div>
      <div className="mt-4 h-2 overflow-hidden rounded-full bg-slate-100">
        <div className="h-full rounded-full bg-amber-400" style={{ width: `${coverage}%` }} />
      </div>
      <div className="mt-4 grid grid-cols-2 gap-3">
        <MiniStat label="商品" value={formatNumber(products)} />
        <MiniStat label="文件" value={formatNumber(documents)} />
      </div>
    </div>
  );
}
