"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import FontSizeToggle from "@/components/font-size-toggle";
import NavLinks from "@/components/nav-links";

export default function SiteHeader() {
  const pathname = usePathname();
  if (pathname === "/") return null;

  const isAdvisor = pathname.startsWith("/advisor");

  return (
    <header className="sticky top-0 z-10 shrink-0 border-b border-slate-200 bg-white/90 backdrop-blur">
      <nav className="flex h-16 w-full items-center gap-4 px-4 md:px-6">
        <Link href="/" className="flex shrink-0 items-center gap-2 text-base font-bold text-slate-950">
          <span className={`h-8 w-8 rounded-lg ${isAdvisor ? "bg-amber-300" : "bg-teal-400"}`} />
          {isAdvisor ? "保險顧問系統" : "AI 保險顧問"}
        </Link>
        <NavLinks />
        <FontSizeToggle />
      </nav>
    </header>
  );
}
