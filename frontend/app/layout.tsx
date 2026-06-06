import type { Metadata } from "next";
import { Geist } from "next/font/google";
import Link from "next/link";
import FontSizeToggle from "@/components/font-size-toggle";
import "./globals.css";

const geist = Geist({ variable: "--font-geist-sans", subsets: ["latin"] });

export const metadata: Metadata = {
  title: "AI 保險顧問",
  description: "站在你這邊的 AI 保險顧問",
};

export default function RootLayout({
  children,
}: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="zh-TW" className={`${geist.variable} h-full antialiased`}>
      <body className="h-full flex flex-col bg-gray-50">
        <header className="shrink-0 bg-white border-b border-gray-200 sticky top-0 z-10">
          <nav className="px-6 h-14 flex items-center gap-8">
            <Link href="/" className="text-lg font-semibold text-blue-700 shrink-0">
              AI 保險顧問
            </Link>
            <div className="flex items-center gap-5 text-sm">
              <Link
                href="/products"
                className="text-gray-600 hover:text-blue-700 transition-colors"
              >
                保險商品
              </Link>
              <Link
                href="/allocation"
                className="text-gray-600 hover:text-blue-700 transition-colors"
              >
                配置建議
              </Link>
              <Link
                href="/health-check"
                className="text-gray-600 hover:text-blue-700 transition-colors"
              >
                需求評估
              </Link>
              <Link
                href="/claims"
                className="text-gray-600 hover:text-blue-700 transition-colors"
              >
                理賠模擬
              </Link>
            </div>
            <div className="ml-auto">
              <FontSizeToggle />
            </div>
          </nav>
        </header>
        <main className="flex-1 min-h-0 overflow-auto">{children}</main>
      </body>
    </html>
  );
}
