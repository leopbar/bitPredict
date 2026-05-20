import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";
import { Providers } from "./providers";
import { Sidebar } from "@/components/layout/sidebar";

const inter = Inter({
  subsets: ["latin"],
  variable: "--font-inter",
  display: "swap",
  weight: ["400", "500", "600", "700"],
});

export const metadata: Metadata = {
  title: "bitPredict — BTC Forecast",
  description: "Bitcoin price forecasting powered by Kronos foundation model.",
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`dark ${inter.variable}`}>
      <body className="bg-[#0A0A0B] text-zinc-100 min-h-screen font-sans">
        <Providers>
          <div className="flex">
            <Sidebar />
            <div className="flex-1 min-w-0">{children}</div>
          </div>
        </Providers>
      </body>
    </html>
  );
}
