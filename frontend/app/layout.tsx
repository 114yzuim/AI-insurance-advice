import type { Metadata } from "next";
import SiteHeader from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 保險顧問系統",
  description: "提供商品查詢與推薦、保單管理、保障健檢與理賠中心的 AI 保險顧問系統。",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-TW" className="h-full antialiased">
      <body className="flex h-full flex-col bg-slate-50">
        <SiteHeader />
        <main className="min-h-0 flex-1 overflow-auto">{children}</main>
      </body>
    </html>
  );
}
