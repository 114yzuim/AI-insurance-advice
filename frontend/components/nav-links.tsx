"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

type NavLink = {
  href: string;
  label: string;
  exact?: boolean;
};

const CUSTOMER_LINKS: NavLink[] = [
  { href: "/policies", label: "我的保單" },
  { href: "/health-check", label: "保障健診" },
  { href: "/claims", label: "理賠中心" },
  { href: "/chat", label: "AI顧問" },
];

const ADVISOR_LINKS: NavLink[] = [
  { href: "/advisor", label: "顧問工作台", exact: true },
  { href: "/advisor/inventory", label: "產品資料庫" },
];

export default function NavLinks() {
  const pathname = usePathname();
  const isAdvisor = pathname.startsWith("/advisor");
  const links = isAdvisor ? ADVISOR_LINKS : CUSTOMER_LINKS;

  return (
    <div className="flex min-w-0 flex-1 items-center gap-1 overflow-x-auto text-sm">
      {links.map(({ href, label, exact }) => {
        const active = exact ? pathname === href : pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            className={`shrink-0 rounded-full px-3 py-2 font-semibold transition ${
              active
                ? "bg-slate-950 text-white"
                : "text-slate-500 hover:bg-slate-100 hover:text-slate-900"
            }`}
          >
            {label}
          </Link>
        );
      })}

      <div className="ml-auto shrink-0">
        {isAdvisor ? (
          <Link
            href="/chat"
            className="rounded-full border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-500 transition hover:border-teal-300 hover:text-teal-700"
          >
            切換客戶模式
          </Link>
        ) : (
          <Link
            href="/advisor"
            className="rounded-full border border-slate-200 px-3 py-2 text-sm font-semibold text-slate-500 transition hover:border-amber-300 hover:text-amber-700"
          >
            顧問工作台
          </Link>
        )}
      </div>
    </div>
  );
}
