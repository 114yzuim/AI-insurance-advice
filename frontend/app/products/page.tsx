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

export default async function ProductsPage() {
  const { categories, companies } = await getFilters();

  return (
    <div className="flex h-full flex-col bg-[#f7faf8]">
      <div className="shrink-0 border-b border-slate-200 bg-white/70 px-5 py-5 backdrop-blur md:px-6">
        <div className="flex flex-col gap-4 lg:flex-row lg:items-end lg:justify-between">
          <div>
            <p className="text-sm font-bold text-teal-700">商品清單</p>
            <h1 className="mt-1 text-3xl font-bold text-slate-950">快速找到適合比較的保險商品</h1>
            <p className="mt-2 text-sm leading-6 text-slate-500">
              先用類別、公司或關鍵字縮小範圍，勾選商品後可在右側請 AI 協助解讀。
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
      <div className="flex-1 min-h-0">
        <ProductList categories={categories} companies={companies} />
      </div>
    </div>
  );
}
