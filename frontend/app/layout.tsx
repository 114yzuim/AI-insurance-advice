import type { Metadata } from "next";
import { Geist } from "next/font/google";
import SiteHeader from "@/components/site-header";
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
        <SiteHeader />
        <main className="flex-1 min-h-0 overflow-auto">{children}</main>
      </body>
    </html>
  );
}
