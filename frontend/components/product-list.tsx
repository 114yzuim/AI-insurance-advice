"use client";

import { useState, useEffect, useCallback } from "react";
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

  const PAGE_SIZE = 12;

  const fetchProducts = useCallback(async () => {
    setLoading(true);
    const params = new URLSearchParams({ page: String(page), page_size: String(PAGE_SIZE) });
    if (keyword) params.set("keyword", keyword);
    if (selectedCategory) params.set("category", selectedCategory);
    if (selectedCompany) params.set("company", selectedCompany);

    const res = await fetch(`/api/products?${params}`);
    const data = await res.json();
    setProducts(data.products);
    setTotal(data.total);
    setLoading(false);
  }, [page, keyword, selectedCategory, selectedCompany]);

  useEffect(() => {
    fetchProducts();
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
    <div className="h-full flex">
      {/* Left: scrollable product area */}
      <div className="flex-1 min-w-0 overflow-y-auto">
        {/* Filter bar */}
        <div className="bg-white border-b border-gray-200 py-4 sticky top-0 z-10">
          <div className="px-4 flex flex-wrap gap-3">
            <input
              type="text"
              placeholder="搜尋商品名稱..."
              value={keyword}
              onChange={handleFilterChange(setKeyword)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm w-52 focus:outline-none focus:ring-2 focus:ring-blue-300"
            />
            <select
              value={selectedCategory}
              onChange={handleFilterChange(setSelectedCategory)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
            >
              <option value="">所有類別</option>
              {categories.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <select
              value={selectedCompany}
              onChange={handleFilterChange(setSelectedCompany)}
              className="border border-gray-300 rounded-lg px-3 py-2 text-sm focus:outline-none focus:ring-2 focus:ring-blue-300"
            >
              <option value="">所有公司</option>
              {companies.map((c) => (
                <option key={c} value={c}>{c}</option>
              ))}
            </select>
            <div className="ml-auto flex items-center gap-3">
              {selectedProducts.length > 0 && (
                <button
                  onClick={() => setSelectedProducts([])}
                  className="text-xs text-gray-400 hover:text-gray-600"
                >
                  清除勾選 ({selectedProducts.length})
                </button>
              )}
              <span className="text-sm text-gray-400">共 {total} 筆</span>
              <button
                onClick={() => setChatOpen((v) => !v)}
                title={chatOpen ? "關閉 AI 詢問面板" : "開啟 AI 詢問面板"}
                className="flex items-center gap-1.5 text-xs px-3 py-1.5 rounded-lg border border-gray-200 text-gray-500 hover:bg-gray-50 hover:border-gray-300 transition-colors"
              >
                <svg className="w-3.5 h-3.5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M8 10h.01M12 10h.01M16 10h.01M9 16H5a2 2 0 01-2-2V6a2 2 0 012-2h14a2 2 0 012 2v8a2 2 0 01-2 2h-5l-3 3z" />
                </svg>
                {chatOpen ? "收起詢問" : "AI 詢問"}
              </button>
            </div>
          </div>
        </div>

        {/* Product grid */}
        <div className="px-4 py-6">
          {loading ? (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
              {Array.from({ length: PAGE_SIZE }).map((_, i) => (
                <div key={i} className="bg-white border border-gray-200 rounded-xl h-44 animate-pulse" />
              ))}
            </div>
          ) : products.length === 0 ? (
            <div className="text-center py-20 text-gray-400">找不到符合條件的商品</div>
          ) : (
            <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-3 gap-4">
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

        {/* Pagination */}
        {totalPages > 1 && (
          <div className="px-4 pb-8 flex justify-center gap-2">
            <button
              onClick={() => setPage((p) => Math.max(1, p - 1))}
              disabled={page === 1}
              className="px-4 py-2 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
            >
              上一頁
            </button>
            <span className="px-4 py-2 text-sm text-gray-500">
              {page} / {totalPages}
            </span>
            <button
              onClick={() => setPage((p) => Math.min(totalPages, p + 1))}
              disabled={page === totalPages}
              className="px-4 py-2 text-sm border border-gray-300 rounded-lg disabled:opacity-40 hover:bg-gray-50"
            >
              下一頁
            </button>
          </div>
        )}
      </div>

      {/* Right: chat panel — always mounted to preserve history, hidden via CSS */}
      <div className={`w-80 lg:w-96 shrink-0 border-l border-gray-200 h-full ${chatOpen ? "" : "hidden"}`}>
        <ProductChatPanel selected={selectedProducts} onDeselect={deselectProduct} />
      </div>
    </div>
  );
}
