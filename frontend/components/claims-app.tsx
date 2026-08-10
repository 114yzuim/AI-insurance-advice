"use client";

import { useEffect, useState } from "react";

interface Product {
  product_id: string;
  product_name: string;
  company: string;
  category: string;
}

interface HoldingItem {
  product_id: string;
  product_name: string;
  company: string;
  category: string;
  amount: string;
}

interface CoverageResult {
  type: string;
  likely: boolean;
  note: string;
}

interface ClaimsResult {
  applicable_coverages: CoverageResult[];
  exclusions_to_check: string[];
  required_documents: string[];
  claim_steps: string[];
  important_notes: string;
  disclaimer: string;
}

const CATEGORIES = ["健康醫療", "壽險保障", "意外傷害", "年金保險", "投資型保險", "還本養老"];

const EXAMPLE_SCENARIOS = [
  "我騎機車上班途中被追撞，手腕骨折，住院開刀 5 天",
  "健康檢查發現乳癌第二期，需要手術和化療",
  "工作時從高處跌落，脊椎受傷造成下半身失能",
  "突發心肌梗塞送急診，加護病房住了 3 天",
];

export default function ClaimsApp() {
  const [scenario, setScenario] = useState("");
  const [holdings, setHoldings] = useState<HoldingItem[]>([]);
  const [loading, setLoading] = useState(false);
  const [result, setResult] = useState<ClaimsResult | null>(null);
  const [error, setError] = useState("");

  const [activeCategory, setActiveCategory] = useState(CATEGORIES[0]);
  const [categoryProducts, setCategoryProducts] = useState<Product[]>([]);
  const [productSearch, setProductSearch] = useState("");
  const [loadingProducts, setLoadingProducts] = useState(false);

  useEffect(() => {
    setLoadingProducts(true);
    setProductSearch("");
    fetch(`/api/products?category=${encodeURIComponent(activeCategory)}&page_size=60`)
      .then((r) => r.json())
      .then((data) => setCategoryProducts(data.products ?? []))
      .catch(() => setCategoryProducts([]))
      .finally(() => setLoadingProducts(false));
  }, [activeCategory]);

  function toggleProduct(p: Product) {
    const exists = holdings.find((h) => h.product_id === p.product_id);
    if (exists) {
      setHoldings((prev) => prev.filter((h) => h.product_id !== p.product_id));
      return;
    }
    setHoldings((prev) => [
      ...prev,
      { product_id: p.product_id, product_name: p.product_name, company: p.company, category: p.category, amount: "" },
    ]);
  }

  function updateAmount(product_id: string, amount: string) {
    setHoldings((prev) =>
      prev.map((h) => (h.product_id === product_id ? { ...h, amount } : h))
    );
  }

  async function handleAnalyze() {
    if (!scenario.trim() || loading) return;
    setLoading(true);
    setError("");
    setResult(null);
    try {
      const res = await fetch("/api/claims", {
        method: "POST",
        headers: { "Content-Type": "application/json" },
        body: JSON.stringify({ scenario, holdings }),
      });
      if (!res.ok) throw new Error();
      setResult(await res.json());
    } catch {
      setError("分析失敗，請確認後端已啟動並重試。");
    } finally {
      setLoading(false);
    }
  }

  function handleReset() {
    setResult(null);
    setScenario("");
    setHoldings([]);
    setError("");
  }

  const filteredProducts = productSearch.trim()
    ? categoryProducts.filter(
        (p) =>
          p.product_name.includes(productSearch) ||
          p.company.includes(productSearch)
      )
    : categoryProducts;

  if (result) {
    return <ResultView result={result} scenario={scenario} holdings={holdings} onReset={handleReset} />;
  }

  return (
    <div className="min-h-full bg-[#f7faf8] px-5 py-8 md:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-6 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-bold text-teal-700">理賠協助</p>
            <h1 className="mt-2 text-3xl font-bold leading-tight text-slate-950 md:text-5xl">
              先把情境說清楚，再整理理賠準備
            </h1>
            <p className="mt-3 max-w-3xl text-base leading-7 text-slate-600">
              描述事故或疾病狀況，也可以勾選已投保商品，AI 會協助整理可能保障、除外條款、文件與流程。
            </p>
          </div>
          <div className="flex gap-2">
            <Badge label="情境分析" />
            <Badge label="文件整理" />
          </div>
        </div>

        <div className="grid gap-5 lg:grid-cols-[minmax(0,1fr)_380px]">
          <section className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-xl shadow-teal-100/70">
            <label className="text-sm font-bold text-slate-800">描述你的理賠情境</label>
            <textarea
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              placeholder="例如：我騎機車出車禍，手腕骨折住院 3 天..."
              rows={8}
              className="mt-3 min-h-56 w-full resize-none rounded-[1.5rem] border border-slate-200 bg-slate-50/70 px-4 py-4 text-base leading-7 text-slate-800 outline-none transition placeholder:text-slate-400 focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            />

            <div className="mt-4 border-t border-slate-100 pt-4">
              <p className="mb-2 text-xs font-bold text-slate-400">快速範例</p>
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_SCENARIOS.map((example) => (
                  <button
                    key={example}
                    onClick={() => setScenario(example)}
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-xs font-bold text-slate-500 transition hover:border-teal-300 hover:bg-teal-50 hover:text-teal-700"
                  >
                    {example.slice(0, 18)}...
                  </button>
                ))}
              </div>
            </div>

            {error && <p className="mt-4 text-sm font-bold text-red-500">{error}</p>}

            <button
              onClick={handleAnalyze}
              disabled={!scenario.trim() || loading}
              className="mt-5 inline-flex w-full items-center justify-center gap-2 rounded-xl bg-slate-950 py-3 text-sm font-bold text-white transition hover:bg-slate-800 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {loading ? (
                <>
                  <SpinnerIcon /> 分析中...
                </>
              ) : (
                "開始模擬"
              )}
            </button>
          </section>

          <aside className="space-y-5">
            <section className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
              <div>
                <p className="text-sm font-bold text-slate-950">已投保商品</p>
                <p className="mt-1 text-xs leading-5 text-slate-400">可不選，留空時會以一般理賠情境分析。</p>
              </div>

              <div className="mt-4 flex flex-wrap gap-1.5">
                {CATEGORIES.map((cat) => (
                  <button
                    key={cat}
                    onClick={() => setActiveCategory(cat)}
                    className={`rounded-full border px-3 py-1.5 text-xs font-bold transition ${
                      activeCategory === cat
                        ? "border-slate-950 bg-slate-950 text-white"
                        : "border-slate-200 text-slate-600 hover:border-teal-300 hover:text-teal-700"
                    }`}
                  >
                    {cat}
                  </button>
                ))}
              </div>

              <input
                value={productSearch}
                onChange={(e) => setProductSearch(e.target.value)}
                placeholder="搜尋商品名稱或公司..."
                className="mt-3 w-full rounded-2xl border border-slate-200 px-3 py-2.5 text-xs text-slate-800 outline-none transition placeholder:text-slate-300 focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              />

              {loadingProducts ? (
                <p className="py-4 text-center text-xs text-slate-400">載入中...</p>
              ) : filteredProducts.length === 0 ? (
                <p className="py-4 text-center text-xs text-slate-400">查無商品</p>
              ) : (
                <div className="mt-3 flex max-h-64 flex-col gap-1.5 overflow-y-auto pr-1">
                  {filteredProducts.map((p) => {
                    const selected = !!holdings.find((h) => h.product_id === p.product_id);
                    return (
                      <button
                        key={p.product_id}
                        onClick={() => toggleProduct(p)}
                        className={`flex w-full items-center justify-between gap-2 rounded-2xl border px-3 py-2 text-left text-xs transition ${
                          selected
                            ? "border-teal-300 bg-teal-50 text-teal-800"
                            : "border-slate-100 text-slate-700 hover:border-teal-200 hover:bg-slate-50"
                        }`}
                      >
                        <span className="truncate font-bold">{p.product_name}</span>
                        <span className="shrink-0 text-slate-400">{p.company}</span>
                      </button>
                    );
                  })}
                </div>
              )}
            </section>

            {holdings.length > 0 && (
              <section className="rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm">
                <p className="text-sm font-bold text-slate-950">已選商品與保障金額</p>
                <div className="mt-3 flex flex-col gap-3">
                  {holdings.map((h) => (
                    <div key={h.product_id} className="rounded-2xl bg-slate-50 p-3">
                      <div className="flex items-start justify-between gap-2">
                        <div className="min-w-0">
                          <p className="truncate text-xs font-bold text-slate-700">{h.product_name}</p>
                          <p className="mt-0.5 text-xs text-slate-400">{h.company}・{h.category}</p>
                        </div>
                        <button
                          onClick={() => setHoldings((prev) => prev.filter((x) => x.product_id !== h.product_id))}
                          className="text-slate-300 transition hover:text-red-400"
                          title="移除商品"
                        >
                          <XIcon />
                        </button>
                      </div>
                      <input
                        value={h.amount}
                        onChange={(e) => updateAmount(h.product_id, e.target.value)}
                        placeholder="保障金額，如：300 萬元"
                        className="mt-2 w-full rounded-xl border border-slate-200 bg-white px-3 py-2 text-xs text-slate-700 outline-none transition placeholder:text-slate-300 focus:border-teal-300"
                      />
                    </div>
                  ))}
                </div>
              </section>
            )}
          </aside>
        </div>
      </div>
    </div>
  );
}

function ResultView({
  result,
  scenario,
  holdings,
  onReset,
}: {
  result: ClaimsResult;
  scenario: string;
  holdings: HoldingItem[];
  onReset: () => void;
}) {
  const likely = result.applicable_coverages.filter((c) => c.likely);
  const unlikely = result.applicable_coverages.filter((c) => !c.likely);

  return (
    <div className="min-h-full bg-[#f7faf8] px-5 py-8 md:px-8">
      <div className="mx-auto max-w-6xl">
        <div className="mb-5 flex flex-col gap-4 rounded-[2rem] border border-slate-200 bg-white p-5 shadow-sm md:flex-row md:items-start md:justify-between">
          <div>
            <p className="text-sm font-bold text-teal-700">模擬結果</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-950">理賠準備清單</h1>
            <p className="mt-2 max-w-3xl text-sm leading-6 text-slate-500">
              <span className="font-bold text-slate-700">情境：</span>{scenario}
            </p>
          </div>
          <button
            onClick={onReset}
            className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 transition hover:bg-slate-50"
          >
            重新模擬
          </button>
        </div>

        {holdings.length > 0 && (
          <div className="mb-5 flex flex-wrap gap-2">
            {holdings.map((h) => (
              <span key={h.product_id} className="rounded-full border border-teal-100 bg-teal-50 px-3 py-1.5 text-xs font-bold text-teal-700">
                {h.product_name}{h.amount ? `（${h.amount}）` : ""}
              </span>
            ))}
          </div>
        )}

        <div className="grid gap-5 lg:grid-cols-2">
          {likely.length > 0 && (
            <Section title="可能理賠的保障" icon={<CheckCircleIcon />} color="green">
              {likely.map((c) => <CoverageCard key={c.type} item={c} />)}
            </Section>
          )}

          {unlikely.length > 0 && (
            <Section title="需確認或通常不賠" icon={<QuestionIcon />} color="gray">
              {unlikely.map((c) => <CoverageCard key={c.type} item={c} />)}
            </Section>
          )}

          {result.exclusions_to_check.length > 0 && (
            <Section title="除外條款與常見拒賠原因" icon={<WarningIcon />} color="amber">
              <ul className="flex flex-col gap-2">
                {result.exclusions_to_check.map((item, i) => (
                  <li key={i} className="flex gap-2 text-sm leading-6 text-amber-900">
                    <span className="mt-0.5 shrink-0 text-amber-500">•</span>{item}
                  </li>
                ))}
              </ul>
            </Section>
          )}

          {result.required_documents.length > 0 && (
            <Section title="需要準備的文件" icon={<DocIcon />} color="blue">
              <ol className="flex flex-col gap-2">
                {result.required_documents.map((item, i) => (
                  <li key={i} className="flex gap-2 text-sm leading-6 text-sky-900">
                    <span className="shrink-0 font-bold text-sky-600">{i + 1}.</span>{item}
                  </li>
                ))}
              </ol>
            </Section>
          )}

          {result.claim_steps.length > 0 && (
            <Section title="理賠流程" icon={<StepsIcon />} color="purple">
              <ol className="flex flex-col gap-2">
                {result.claim_steps.map((item, i) => (
                  <li key={i} className="flex gap-3 text-sm leading-6 text-violet-900">
                    <span className="mt-0.5 flex h-5 w-5 shrink-0 items-center justify-center rounded-full bg-violet-200 text-xs font-bold text-violet-700">
                      {i + 1}
                    </span>
                    {item}
                  </li>
                ))}
              </ol>
            </Section>
          )}

          {result.important_notes && (
            <div className="rounded-[1.5rem] border border-slate-200 bg-white p-4 text-sm leading-7 text-slate-600">
              <span className="font-bold text-slate-800">補充說明：</span>
              {result.important_notes}
            </div>
          )}
        </div>

        <p className="mt-5 text-center text-xs text-slate-400">{result.disclaimer}</p>
      </div>
    </div>
  );
}

function Badge({ label }: { label: string }) {
  return (
    <span className="rounded-full bg-white px-3 py-1.5 text-sm font-bold text-teal-700 shadow-sm ring-1 ring-teal-100">
      {label}
    </span>
  );
}

function Section({
  title,
  icon,
  color,
  children,
}: {
  title: string;
  icon: React.ReactNode;
  color: "green" | "amber" | "blue" | "purple" | "gray";
  children: React.ReactNode;
}) {
  const styles = {
    green: "border-emerald-200 bg-emerald-50",
    amber: "border-amber-200 bg-amber-50",
    blue: "border-sky-200 bg-sky-50",
    purple: "border-violet-200 bg-violet-50",
    gray: "border-slate-200 bg-white",
  };
  const titleStyles = {
    green: "text-emerald-800",
    amber: "text-amber-800",
    blue: "text-sky-800",
    purple: "text-violet-800",
    gray: "text-slate-700",
  };
  return (
    <section className={`rounded-[1.5rem] border p-4 shadow-sm ${styles[color]}`}>
      <div className={`mb-3 flex items-center gap-2 text-sm font-bold ${titleStyles[color]}`}>
        {icon}{title}
      </div>
      {children}
    </section>
  );
}

function CoverageCard({ item }: { item: CoverageResult }) {
  return (
    <div className="mb-2 flex items-start gap-2 last:mb-0">
      <span className={`mt-0.5 shrink-0 rounded-full px-2 py-0.5 text-xs font-bold ${
        item.likely ? "bg-emerald-200 text-emerald-800" : "bg-slate-200 text-slate-600"
      }`}>
        {item.type}
      </span>
      <span className="text-sm leading-6 text-slate-700">{item.note}</span>
    </div>
  );
}

function SpinnerIcon() {
  return (
    <svg className="animate-spin" width="16" height="16" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 12a9 9 0 1 1-6.219-8.56" />
    </svg>
  );
}

function XIcon() {
  return (
    <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5">
      <line x1="18" y1="6" x2="6" y2="18" />
      <line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}

function CheckCircleIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-emerald-600">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" />
      <polyline points="22,4 12,14.01 9,11.01" />
    </svg>
  );
}

function WarningIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-amber-600">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}

function DocIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-sky-600">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14,2 14,8 20,8" />
      <line x1="16" y1="13" x2="8" y2="13" />
      <line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}

function StepsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-violet-600">
      <line x1="8" y1="6" x2="21" y2="6" />
      <line x1="8" y1="12" x2="21" y2="12" />
      <line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" />
      <line x1="3" y1="12" x2="3.01" y2="12" />
      <line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}

function QuestionIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-slate-500">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" />
      <line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
