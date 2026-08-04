import type { Metadata } from "next";
import { Inter } from "next/font/google";
import { ChatWidgetToggle } from "@/components/chat-widget-toggle";
import { Gnb } from "@/components/gnb";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "TFT Hideout",
  description: "TFT 메타 정보 sLLM + RAG 서비스",
};

export default function RootLayout({ children }: LayoutProps<"/">) {
  return (
    <html lang="ko" className={`${inter.variable} h-full antialiased`}>
      <body className="flex min-h-full flex-col font-sans">
        <Gnb />
        <main className="mx-auto w-full max-w-6xl flex-1 px-4 py-8 md:px-10">
          {children}
        </main>
        <ChatWidgetToggle />
      </body>
    </html>
  );
}
