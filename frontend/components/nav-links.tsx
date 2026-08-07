"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const CUSTOMER_LINKS = [
  { href: "/chat", label: "AI 顧問" },
  { href: "/products", label: "保險商品" },
  { href: "/health-check", label: "需求評估" },
  { href: "/claims", label: "理賠模擬" },
];

const ADVISOR_LINKS = [
  { href: "/advisor", label: "客戶列表", exact: true },
];

export default function NavLinks() {
  const pathname = usePathname();
  const isAdvisor = pathname.startsWith("/advisor");
  const links = isAdvisor ? ADVISOR_LINKS : CUSTOMER_LINKS;

  return (
    <div className="flex items-center gap-5 text-sm flex-1">
      {links.map(({ href, label, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`transition-colors font-medium ${
              active
                ? "text-blue-700 underline underline-offset-4 decoration-2"
                : "text-gray-500 hover:text-blue-700"
            }`}
          >
            {label}
          </Link>
        );
      })}

      <div className="ml-auto">
        {isAdvisor ? (
          <Link href="/chat" className="text-xs text-gray-400 hover:text-blue-600 transition-colors border border-gray-200 rounded-lg px-3 py-1.5">
            ← 客戶入口
          </Link>
        ) : (
          <Link href="/advisor" className="text-xs text-gray-400 hover:text-emerald-600 transition-colors border border-gray-200 rounded-lg px-3 py-1.5">
            業務員工具 →
          </Link>
        )}
      </div>
    </div>
  );
}
