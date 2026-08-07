"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import FontSizeToggle from "@/components/font-size-toggle";
import NavLinks from "@/components/nav-links";

export default function SiteHeader() {
  const pathname = usePathname();
  if (pathname === "/") return null;

  return (
    <header className="shrink-0 bg-white border-b border-gray-200 sticky top-0 z-10">
      <nav className="px-6 h-14 flex items-center gap-8">
        <Link href="/" className="text-lg font-semibold text-blue-700 shrink-0">
          {pathname.startsWith("/advisor") ? "業務員操作平台" : "保險顧問平台"}
        </Link>
        <NavLinks />
        <div>
          <FontSizeToggle />
        </div>
      </nav>
    </header>
  );
}
