import type { Metadata } from "next";
import SiteHeader from "@/components/site-header";
import "./globals.css";

export const metadata: Metadata = {
  title: "AI 保險顧問平台",
  description: "集中管理個人保單，讓 AI 協助保障健診、理賠判讀與個人化保險諮詢。",
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
