"use client";

import { useState, useEffect } from "react";

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

  // Product selector state
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
    } else {
      setHoldings((prev) => [
        ...prev,
        { product_id: p.product_id, product_name: p.product_name, company: p.company, category: p.category, amount: "" },
      ]);
    }
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

  return (
    <div className="max-w-2xl mx-auto px-4 py-10">
      <div className="mb-8 text-center">
        <h1 className="text-2xl font-semibold text-gray-800 mb-1">理賠情境模擬</h1>
        <p className="text-sm text-gray-500">描述你的事故或疾病情境，AI 分析可能的理賠狀況</p>
      </div>

      {!result ? (
        <>
          {/* Scenario input */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-4">
            <label className="block text-sm font-medium text-gray-700 mb-2">描述你的情境</label>
            <textarea
              value={scenario}
              onChange={(e) => setScenario(e.target.value)}
              placeholder="例如：我騎機車出車禍，手腕骨折住院 3 天…"
              rows={4}
              className="w-full resize-none text-sm text-gray-800 placeholder-gray-400 focus:outline-none leading-relaxed"
            />
            <div className="mt-3 pt-3 border-t border-gray-100">
              <p className="text-xs text-gray-400 mb-2">快速範例</p>
              <div className="flex flex-wrap gap-1.5">
                {EXAMPLE_SCENARIOS.map((ex) => (
                  <button
                    key={ex}
                    onClick={() => setScenario(ex)}
                    className="text-xs px-2.5 py-1 rounded-full border border-gray-200 text-gray-500 hover:border-blue-300 hover:text-blue-700 hover:bg-blue-50 transition-colors"
                  >
                    {ex.slice(0, 18)}…
                  </button>
                ))}
              </div>
            </div>
          </div>

          {/* Product selector */}
          <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-4">
            <p className="text-sm font-medium text-gray-700 mb-1">
              你持有哪些保險？
              <span className="text-gray-400 font-normal ml-1">（可不選，留空則全面分析）</span>
            </p>

            {/* Category tabs */}
            <div className="flex gap-1.5 mt-3 mb-3 flex-wrap">
              {CATEGORIES.map((cat) => (
                <button
                  key={cat}
                  onClick={() => setActiveCategory(cat)}
                  className={`text-xs px-3 py-1.5 rounded-full border transition-colors ${
                    activeCategory === cat
                      ? "bg-blue-700 text-white border-blue-700"
                      : "border-gray-200 text-gray-600 hover:border-blue-300 hover:text-blue-700"
                  }`}
                >
                  {cat}
                </button>
              ))}
            </div>

            {/* Search */}
            <input
              value={productSearch}
              onChange={(e) => setProductSearch(e.target.value)}
              placeholder="搜尋商品名稱或公司…"
              className="w-full px-3 py-2 text-xs rounded-xl border border-gray-200 focus:outline-none focus:border-blue-300 mb-3 placeholder-gray-300"
            />

            {/* Product list */}
            {loadingProducts ? (
              <p className="text-xs text-gray-400 text-center py-3">載入中…</p>
            ) : filteredProducts.length === 0 ? (
              <p className="text-xs text-gray-400 text-center py-3">查無商品</p>
            ) : (
              <div className="max-h-52 overflow-y-auto flex flex-col gap-1 pr-1">
                {filteredProducts.map((p) => {
                  const selected = !!holdings.find((h) => h.product_id === p.product_id);
                  return (
                    <button
                      key={p.product_id}
                      onClick={() => toggleProduct(p)}
                      className={`w-full text-left px-3 py-2 rounded-xl border text-xs transition-colors flex items-center justify-between gap-2 ${
                        selected
                          ? "bg-blue-50 border-blue-400 text-blue-800"
                          : "border-gray-100 text-gray-700 hover:border-blue-200 hover:bg-gray-50"
                      }`}
                    >
                      <span className="truncate">{p.product_name}</span>
                      <span className="shrink-0 text-gray-400">{p.company}</span>
                    </button>
                  );
                })}
              </div>
            )}
          </div>

          {/* Holdings with amount inputs */}
          {holdings.length > 0 && (
            <div className="bg-white rounded-2xl border border-gray-200 shadow-sm p-5 mb-5">
              <p className="text-sm font-medium text-gray-700 mb-3">已選保險 — 填入保障金額（選填）</p>
              <div className="flex flex-col gap-3">
                {holdings.map((h) => (
                  <div key={h.product_id} className="flex items-center gap-3">
                    <div className="flex-1 min-w-0">
                      <p className="text-xs font-medium text-gray-700 truncate">{h.product_name}</p>
                      <p className="text-xs text-gray-400">{h.company}・{h.category}</p>
                    </div>
                    <div className="flex items-center gap-2 shrink-0">
                      <input
                        value={h.amount}
                        onChange={(e) => updateAmount(h.product_id, e.target.value)}
                        placeholder="如：300 萬元"
                        className="w-28 px-2.5 py-1.5 text-xs rounded-lg border border-gray-200 focus:outline-none focus:border-blue-300 placeholder-gray-300"
                      />
                      <button
                        onClick={() => setHoldings((prev) => prev.filter((x) => x.product_id !== h.product_id))}
                        className="p-1 text-gray-300 hover:text-red-400 transition-colors"
                      >
                        <XIcon />
                      </button>
                    </div>
                  </div>
                ))}
              </div>
            </div>
          )}

          {error && <p className="mb-3 text-sm text-red-500 text-center">{error}</p>}

          <button
            onClick={handleAnalyze}
            disabled={!scenario.trim() || loading}
            className="w-full py-3 bg-blue-700 text-white rounded-xl font-medium text-sm hover:bg-blue-800 disabled:opacity-40 disabled:cursor-not-allowed transition-colors"
          >
            {loading ? (
              <span className="flex items-center justify-center gap-2">
                <SpinnerIcon /> 分析中…
              </span>
            ) : (
              "開始模擬"
            )}
          </button>
        </>
      ) : (
        <ResultView result={result} scenario={scenario} holdings={holdings} onReset={handleReset} />
      )}
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
    <div className="flex flex-col gap-4">
      <div className="bg-gray-100 rounded-xl px-4 py-3 text-sm text-gray-600 leading-relaxed">
        <span className="font-medium text-gray-700">情境：</span>{scenario}
      </div>

      {holdings.length > 0 && (
        <div className="flex flex-wrap gap-1.5">
          {holdings.map((h) => (
            <span key={h.product_id} className="text-xs px-2.5 py-1 bg-blue-50 text-blue-700 rounded-full border border-blue-200">
              {h.product_name}{h.amount ? `（${h.amount}）` : ""}
            </span>
          ))}
        </div>
      )}

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
          <ul className="flex flex-col gap-1.5">
            {result.exclusions_to_check.map((e, i) => (
              <li key={i} className="flex gap-2 text-sm text-amber-900">
                <span className="shrink-0 mt-0.5 text-amber-500">•</span>{e}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {result.required_documents.length > 0 && (
        <Section title="需要準備的文件" icon={<DocIcon />} color="blue">
          <ul className="flex flex-col gap-1.5">
            {result.required_documents.map((d, i) => (
              <li key={i} className="flex gap-2 text-sm text-blue-900">
                <span className="shrink-0 font-medium text-blue-500">{i + 1}.</span>{d}
              </li>
            ))}
          </ul>
        </Section>
      )}

      {result.claim_steps.length > 0 && (
        <Section title="理賠流程" icon={<StepsIcon />} color="purple">
          <ol className="flex flex-col gap-2">
            {result.claim_steps.map((s, i) => (
              <li key={i} className="flex gap-3 text-sm text-purple-900">
                <span className="shrink-0 w-5 h-5 rounded-full bg-purple-200 text-purple-700 text-xs font-bold flex items-center justify-center mt-0.5">
                  {i + 1}
                </span>
                {s}
              </li>
            ))}
          </ol>
        </Section>
      )}

      {result.important_notes && (
        <div className="text-sm text-gray-600 bg-gray-50 rounded-xl px-4 py-3 leading-relaxed border border-gray-200">
          <span className="font-medium text-gray-700">補充說明：</span>
          {result.important_notes}
        </div>
      )}

      <p className="text-xs text-gray-400 text-center">{result.disclaimer}</p>

      <button
        onClick={onReset}
        className="w-full py-2.5 border border-gray-200 rounded-xl text-sm text-gray-600 hover:bg-gray-50 transition-colors"
      >
        重新模擬
      </button>
    </div>
  );
}

function Section({
  title, icon, color, children,
}: {
  title: string;
  icon: React.ReactNode;
  color: "green" | "amber" | "blue" | "purple" | "gray";
  children: React.ReactNode;
}) {
  const styles = {
    green:  "bg-green-50 border-green-200",
    amber:  "bg-amber-50 border-amber-200",
    blue:   "bg-blue-50 border-blue-200",
    purple: "bg-purple-50 border-purple-200",
    gray:   "bg-gray-50 border-gray-200",
  };
  const titleStyles = {
    green:  "text-green-800",
    amber:  "text-amber-800",
    blue:   "text-blue-800",
    purple: "text-purple-800",
    gray:   "text-gray-700",
  };
  return (
    <div className={`rounded-2xl border p-4 ${styles[color]}`}>
      <div className={`flex items-center gap-2 font-medium text-sm mb-3 ${titleStyles[color]}`}>
        {icon}{title}
      </div>
      {children}
    </div>
  );
}

function CoverageCard({ item }: { item: CoverageResult }) {
  return (
    <div className="flex items-start gap-2 mb-2 last:mb-0">
      <span className={`shrink-0 mt-0.5 text-xs font-bold px-1.5 py-0.5 rounded ${
        item.likely ? "bg-green-200 text-green-800" : "bg-gray-200 text-gray-600"
      }`}>
        {item.type}
      </span>
      <span className="text-sm text-gray-700 leading-relaxed">{item.note}</span>
    </div>
  );
}

// ─── Icons ────────────────────────────────────────────────────────────────────
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
      <line x1="18" y1="6" x2="6" y2="18" /><line x1="6" y1="6" x2="18" y2="18" />
    </svg>
  );
}
function CheckCircleIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-green-600">
      <path d="M22 11.08V12a10 10 0 1 1-5.93-9.14" /><polyline points="22,4 12,14.01 9,11.01" />
    </svg>
  );
}
function WarningIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-amber-600">
      <path d="M10.29 3.86L1.82 18a2 2 0 0 0 1.71 3h16.94a2 2 0 0 0 1.71-3L13.71 3.86a2 2 0 0 0-3.42 0z" />
      <line x1="12" y1="9" x2="12" y2="13" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
function DocIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-blue-600">
      <path d="M14 2H6a2 2 0 0 0-2 2v16a2 2 0 0 0 2 2h12a2 2 0 0 0 2-2V8z" />
      <polyline points="14,2 14,8 20,8" />
      <line x1="16" y1="13" x2="8" y2="13" /><line x1="16" y1="17" x2="8" y2="17" />
    </svg>
  );
}
function StepsIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-purple-600">
      <line x1="8" y1="6" x2="21" y2="6" /><line x1="8" y1="12" x2="21" y2="12" /><line x1="8" y1="18" x2="21" y2="18" />
      <line x1="3" y1="6" x2="3.01" y2="6" /><line x1="3" y1="12" x2="3.01" y2="12" /><line x1="3" y1="18" x2="3.01" y2="18" />
    </svg>
  );
}
function QuestionIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2.5" className="text-gray-500">
      <circle cx="12" cy="12" r="10" />
      <path d="M9.09 9a3 3 0 0 1 5.83 1c0 2-3 3-3 3" /><line x1="12" y1="17" x2="12.01" y2="17" />
    </svg>
  );
}
