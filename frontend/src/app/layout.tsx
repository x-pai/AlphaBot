import type { Metadata } from "next";
import { Geist, Geist_Mono } from "next/font/google";
import "./globals.css";
import IndexedDBInitializer from "../components/IndexedDBInitializer";
import { AuthProvider } from "@/lib/contexts/AuthContext";
import AuthGuard from "@/components/AuthGuard";

const geistSans = Geist({
  variable: "--font-geist-sans",
  subsets: ["latin"],
});

const geistMono = Geist_Mono({
  variable: "--font-geist-mono",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "AlphaBot - 你的智能股票分析助手",
  description: "使用AI技术分析股票市场，提供实时数据、图表和智能投资建议，帮助您做出更明智的投资决策。",
  keywords: "股票分析, AI投资, 股票助手, 智能投资, 股票市场, 投资建议",
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="zh-CN" suppressHydrationWarning>
      <body
        className={`${geistSans.variable} ${geistMono.variable} antialiased`}
      >
        <AuthProvider>
          <AuthGuard>
            <IndexedDBInitializer />
            {children}
          </AuthGuard>
        </AuthProvider>
      </body>
    </html>
  );
}
