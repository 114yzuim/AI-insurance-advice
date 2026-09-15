import ProductList from "@/components/product-list";

const BACKEND = process.env.BACKEND_URL ?? "http://127.0.0.1:8000";

async function getFilters() {
  try {
    const [catRes, compRes] = await Promise.all([
      fetch(`${BACKEND}/products/categories`, { cache: "no-store" }),
      fetch(`${BACKEND}/products/companies`, { cache: "no-store" }),
    ]);
    if (!catRes.ok || !compRes.ok) return { categories: [], companies: [] };
    const { categories } = await catRes.json();
    const { companies } = await compRes.json();
    return { categories, companies };
  } catch {
    return { categories: [], companies: [] };
  }
}

export const metadata = { title: "商品查詢與推薦 | AI 保險顧問" };

export default async function ProductsPage() {
  const { categories, companies } = await getFilters();

  return (
    <div className="flex h-full flex-col bg-[#f7faf8]">
      <div className="shrink-0 border-b border-slate-200 bg-white/70 px-5 py-5 backdrop-blur md:px-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-bold text-teal-700">商品查詢與推薦</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-950">查詢商品，勾選後請 AI 協助推薦</h1>
            <p className="mt-2 max-w-4xl text-sm leading-6 text-slate-500">
              可依關鍵字、商品類別或保險公司快速檢索商品。選取候選商品後，在右側輸入客戶基本資料、需求與預算，AI 會協助比較適配度與建議說法。
            </p>
          </div>
          <div className="flex flex-wrap gap-2">
            <span className="rounded-full bg-teal-50 px-3 py-1.5 text-sm font-bold text-teal-700">
              {companies.length} 家公司
            </span>
            <span className="rounded-full bg-sky-50 px-3 py-1.5 text-sm font-bold text-sky-700">
              {categories.length} 種類別
            </span>
          </div>
        </div>
      </div>
      <div className="min-h-0 flex-1">
        <ProductList categories={categories} companies={companies} />
      </div>
    </div>
  );
}
