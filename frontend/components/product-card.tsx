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
  壽險保障: "bg-blue-100 text-blue-700",
  健康醫療: "bg-green-100 text-green-700",
  投資型保險: "bg-purple-100 text-purple-700",
  意外傷害: "bg-orange-100 text-orange-700",
  還本養老: "bg-yellow-100 text-yellow-700",
  年金保險: "bg-pink-100 text-pink-700",
  其他: "bg-gray-100 text-gray-600",
};

export default function ProductCard({ product, checked = false, onToggle }: ProductCardProps) {
  const categoryColor =
    CATEGORY_COLOR[product.category] ?? "bg-gray-100 text-gray-600";

  return (
    <div
      className={`bg-white border rounded-xl p-5 flex flex-col gap-3 hover:shadow-md transition-all cursor-pointer ${
        checked ? "border-blue-400 ring-2 ring-blue-200 shadow-sm" : "border-gray-200"
      }`}
      onClick={onToggle}
    >
      <div className="flex items-start justify-between gap-2">
        <div className="flex items-center gap-2">
          <input
            type="checkbox"
            checked={checked}
            onChange={onToggle}
            onClick={(e) => e.stopPropagation()}
            className="w-4 h-4 accent-blue-600 cursor-pointer shrink-0"
          />
          <span className={`text-xs px-2 py-1 rounded-full font-medium ${categoryColor}`}>
            {product.category}
          </span>
        </div>
        <span className="text-xs text-gray-400">{product.currency}</span>
      </div>
      <h3 className="text-sm font-semibold text-gray-800 leading-snug">
        {product.product_name}
      </h3>
      <p className="text-xs text-gray-500">{product.company}</p>
      <div className="mt-auto pt-2 flex gap-2" onClick={(e) => e.stopPropagation()}>
        <Link
          href={`/translate?url=${encodeURIComponent(product.download_urls[0])}&name=${encodeURIComponent(product.product_name)}`}
          className="flex-1 text-center text-xs py-2 bg-blue-50 text-blue-700 rounded-lg hover:bg-blue-100 transition-colors font-medium"
        >
          白話文解釋
        </Link>
        <a
          href={product.download_urls[0]}
          target="_blank"
          rel="noopener noreferrer"
          className="text-xs py-2 px-3 border border-gray-200 text-gray-500 rounded-lg hover:bg-gray-50 transition-colors"
        >
          原始條款
        </a>
      </div>
    </div>
  );
}
