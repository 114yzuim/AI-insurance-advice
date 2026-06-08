"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

const LINKS = [
  { href: "/products", label: "保險商品" },
  { href: "/health-check", label: "需求評估" },
  { href: "/claims", label: "理賠模擬" },
  { href: "/allocation", label: "退休規劃" },
];

export default function NavLinks() {
  const pathname = usePathname();

  return (
    <div className="flex items-center gap-5 text-sm">
      {LINKS.map(({ href, label }) => {
        const active = pathname.startsWith(href);
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
    </div>
  );
}
