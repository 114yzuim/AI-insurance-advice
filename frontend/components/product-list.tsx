"use client";

import { useCallback, useEffect, useState } from "react";
import ProductCard from "./product-card";
import ProductChatPanel from "./product-chat-panel";

interface Product {
  product_id: string;
  product_name: string;
  company: string;
  category: string;
  currency: string;
  download_urls: string[];
}

interface ProductListProps {
  categories: string[];
  companies: string[];
}

const PAGE_SIZE = 12;

export default function ProductList({ categories, companies }: ProductListProps) {
  const [products, setProducts] = useState<Product[]>([]);
  const [total, setTotal] = useState(0);
  const [page, setPage] = useState(1);
  const [loading, setLoading] = useState(true);

  const [keyword, setKeyword] = useState("");
  const [selectedCategory, setSelectedCategory] = useState("");
  const [selectedCompany, setSelectedCompany] = useState("");

  const [selectedProducts, setSelectedProducts] = useState<Product[]>([]);
  const [chatOpen, setChatOpen] = useState(true);

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (keyword) params.set("keyword", keyword);
    if (selectedCategory) params.set("category", selectedCategory);
    if (selectedCompany) params.set("company", selectedCompany);

    try {
      const res = await fetch(`/api/products?${params}`);
      const data = await res.json();
      setProducts(data.products ?? []);
      setTotal(data.total ?? 0);
    } catch {
      setProducts([]);
      setTotal(0);
    } finally {
      setLoading(false);
    }
  }, [page, keyword, selectedCategory, selectedCompany]);

  useEffect(() => {
    queueMicrotask(() => {
      fetchProducts();
    });
  }, [fetchProducts]);

  const totalPages = Math.ceil(total / PAGE_SIZE);

  function handleFilterChange(setter: (v: string) => void) {
    return (e: React.ChangeEvent<HTMLSelectElement | HTMLInputElement>) => {
      setter(e.target.value);
      setPage(1);
    };
  }

  function toggleProduct(p: Product) {
    setSelectedProducts((prev) =>
      prev.find((s) => s.product_id === p.product_id)
        ? prev.filter((s) => s.product_id !== p.product_id)
        : [...prev, p]
    );
  }

  function deselectProduct(id: string) {
    setSelectedProducts((prev) => prev.filter((p) => p.product_id !== id));
  }

  return (
    <div className="flex h-full min-h-0 bg-[#f7faf8]">
      <div className="min-w-0 flex-1 overflow-y-auto px-4 pb-6 md:px-6">
        <div className="sticky top-0 z-10 -mx-4 border-b border-slate-200 bg-[#f7faf8]/95 px-4 py-4 backdrop-blur md:-mx-6 md:px-6">
          <div className="grid gap-3 xl:grid-cols-[minmax(260px,1fr)_220px_220px_auto]">
            <label className="relative">
              <span className="pointer-events-none absolute left-3 top-1/2 -translate-y-1/2 text-slate-400">
                <SearchIcon />
              </span>
              <input
                type="text"
                placeholder="搜尋商品名稱..."
                value={keyword}
                onChange={handleFilterChange(setKeyword)}
                className="h-11 w-full rounded-2xl border border-slate-200 bg-white py-2 pl-10 pr-3 text-sm text-slate-800 shadow-sm outline-none transition placeholder:text-slate-400 focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
              />
            </label>

            <select
              value={selectedCategory}
              onChange={handleFilterChange(setSelectedCategory)}
              className="h-11 rounded-2xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 shadow-sm outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            >
              <option value="">所有類別</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>

            <select
              value={selectedCompany}
              onChange={handleFilterChange(setSelectedCompany)}
              className="h-11 rounded-2xl border border-slate-200 bg-white px-3 text-sm font-medium text-slate-600 shadow-sm outline-none transition focus:border-teal-300 focus:ring-4 focus:ring-teal-100"
            >
              <option value="">所有公司</option>
              {companies.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>

            <div className="flex items-center justify-between gap-3 xl:justify-end">
              <span className="whitespace-nowrap rounded-full bg-white px-3 py-2 text-sm font-bold text-slate-500 shadow-sm ring-1 ring-slate-100">
                共 {total} 筆
              </span>
              {selectedProducts.length > 0 && (
                <button
                  onClick={() => setSelectedProducts([])}
                  className="whitespace-nowrap text-sm font-bold text-slate-400 transition hover:text-rose-500"
                >
                  清除 {selectedProducts.length} 筆
                </button>
              )}
              <button
                onClick={() => setChatOpen((v) => !v)}
                title={chatOpen ? "關閉 AI 詢問面板" : "開啟 AI 詢問面板"}
                className="inline-flex h-11 items-center gap-2 rounded-2xl border border-slate-200 bg-white px-4 text-sm font-bold text-slate-600 shadow-sm transition hover:border-teal-200 hover:text-teal-700"
              >
                <MessageIcon />
                {chatOpen ? "收起 AI" : "AI 詢問"}
              </button>
            </div>
          </div>
        </div>

        <div className="py-6">
          {loading ? (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {Array.from({ length: PAGE_SIZE }).map((_, i) => (
                <div key={i} className="h-52 animate-pulse rounded-3xl border border-slate-200 bg-white" />
              ))}
            </div>
          ) : products.length === 0 ? (
            <div className="rounded-3xl border border-dashed border-slate-300 bg-white px-6 py-16 text-center">
              <p className="text-base font-bold text-slate-700">找不到符合條件的商品</p>
              <p className="mt-2 text-sm text-slate-400">可以清除篩選，或改用較短的商品關鍵字。</p>
            </div>
          ) : (
            <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-3 2xl:grid-cols-4">
              {products.map((p) => (
                <ProductCard
                  key={p.product_id}
                  product={p}
                  checked={!!selectedProducts.find((s) => s.product_id === p.product_id)}
                  onToggle={() => toggleProduct(p)}
                />
              ))}
            </div>
          )}
        </div>

        {totalPages > 1 && (
          <div className="flex justify-center gap-2 pb-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              上一頁
            </button>
            <span className="rounded-xl bg-white px-4 py-2 text-sm font-bold text-slate-500 ring-1 ring-slate-100">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="rounded-xl border border-slate-200 bg-white px-4 py-2 text-sm font-bold text-slate-600 transition hover:bg-slate-50 disabled:cursor-not-allowed disabled:opacity-40"
            >
              下一頁
            </button>
          </div>
        )}
      </div>

      <div className={`hidden h-full w-80 shrink-0 border-l border-slate-200 bg-white xl:block 2xl:w-96 ${chatOpen ? "" : "xl:hidden"}`}>
        <ProductChatPanel selected={selectedProducts} onDeselect={deselectProduct} />
      </div>
    </div>
  );
}

function SearchIcon() {
  return (
    <svg width="17" height="17" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <circle cx="11" cy="11" r="8" />
      <path d="M21 21l-4.35-4.35" />
    </svg>
  );
}

function MessageIcon() {
  return (
    <svg width="15" height="15" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
      <path d="M21 15a4 4 0 0 1-4 4H8l-5 3V7a4 4 0 0 1 4-4h10a4 4 0 0 1 4 4z" />
    </svg>
  );
}
