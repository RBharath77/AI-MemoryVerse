import type { Metadata } from "next";
import "./globals.css";
import { Providers } from "./providers";

export const metadata: Metadata = {
  title: "AI-MemoryVerse — Personal AI Memory & Knowledge Intelligence Platform",
  description:
    "Remember. Connect. Understand. Retrieve. AI-MemoryVerse transforms your conversations, documents, and notes into an intelligent, persistent external brain.",
  keywords: [
    "AI Memory",
    "Personal Knowledge Management",
    "RAG",
    "Second Brain",
    "Knowledge Graph",
    "FastAPI",
    "Next.js",
  ],
  authors: [{ name: "AI-MemoryVerse Team" }],
  openGraph: {
    title: "AI-MemoryVerse — Intelligent Personal Memory & Knowledge Platform",
    description: "Your persistent external brain powered by source-grounded AI.",
    siteName: "AI-MemoryVerse",
    type: "website",
  },
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className="dark">
      <body className="bg-navy-950 text-slate-100 antialiased selection:bg-cyan-500/30 selection:text-cyan-200">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
