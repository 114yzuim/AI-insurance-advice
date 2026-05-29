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
    <div className="h-full flex flex-col">
      <div className="px-6 py-5 shrink-0 bg-gray-50">
        <h1 className="text-2xl font-bold text-gray-900">保險商品總覽</h1>
        <p className="text-gray-500 text-sm mt-1">
          涵蓋 {companies.length} 家壽險公司，勾選商品後可在右側詢問 AI
        </p>
      </div>
      <div className="flex-1 min-h-0">
        <ProductList categories={categories} companies={companies} />
      </div>
    </div>
  );
}
