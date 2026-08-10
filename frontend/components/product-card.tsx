import Link from "next/link";

interface Product {
  product_id: string;
  product_name: string;
  company: string;
  category: string;
  currency: string;
  download_urls: string[];
}

interface ProductCardProps {
  product: Product;
  checked?: boolean;
  onToggle?: () => void;
}

const CATEGORY_COLOR: Record<string, string> = {
  壽險保障: "bg-sky-100 text-sky-700",
  健康醫療: "bg-emerald-100 text-emerald-700",
  投資型保險: "bg-violet-100 text-violet-700",
  意外傷害: "bg-orange-100 text-orange-700",
  還本養老: "bg-amber-100 text-amber-700",
  年金保險: "bg-rose-100 text-rose-700",
  其他: "bg-slate-100 text-slate-600",
};

export default function ProductCard({ product, checked = false, onToggle }: ProductCardProps) {
  const categoryColor = CATEGORY_COLOR[product.category] ?? "bg-slate-100 text-slate-600";
  const firstUrl = product.download_urls[0] ?? "";

  return (
    <article
      className={`group flex min-h-52 cursor-pointer flex-col rounded-3xl border bg-white p-4 shadow-sm transition hover:-translate-y-0.5 hover:shadow-md ${
        checked ? "border-teal-300 ring-4 ring-teal-100" : "border-slate-200"
      }`}
      onClick={onToggle}
    >
      <div className="flex items-start justify-between gap-3">
        <div className="flex min-w-0 items-center gap-2">
          <span
            className={`flex h-5 w-5 shrink-0 items-center justify-center rounded-lg border transition ${
              checked ? "border-teal-600 bg-teal-600 text-white" : "border-slate-300 bg-white text-transparent"
            }`}
          >
            <CheckIcon />
          </span>
          <span className={`truncate rounded-full px-2.5 py-1 text-xs font-bold ${categoryColor}`}>
            {product.category}
          </span>
        </div>
        <span className="shrink-0 rounded-full bg-slate-50 px-2 py-1 text-xs font-semibold text-slate-400">
          {product.currency}
        </span>
      </div>

      <h3 className="mt-4 line-clamp-3 text-base font-bold leading-7 text-slate-950">
        {product.product_name}
      </h3>
      <p className="mt-2 text-sm font-medium text-slate-500">{product.company}</p>

      <div className="mt-auto flex gap-2 pt-4" onClick={(e) => e.stopPropagation()}>
        <Link
          href={`/translate?url=${encodeURIComponent(firstUrl)}&name=${encodeURIComponent(product.product_name)}`}
          className="inline-flex flex-1 items-center justify-center rounded-xl bg-teal-50 px-3 py-2 text-sm font-bold text-teal-700 transition hover:bg-teal-100"
        >
          白話解釋
        </Link>
        {firstUrl && (
          <a
            href={firstUrl}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center justify-center rounded-xl border border-slate-200 px-3 py-2 text-sm font-bold text-slate-500 transition hover:bg-slate-50 hover:text-slate-800"
          >
            條款
          </a>
        )}
      </div>
    </article>
  );
}

function CheckIcon() {
  return (
    <svg width="13" height="13" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="3">
      <polyline points="20,6 9,17 4,12" />
    </svg>
  );
}
