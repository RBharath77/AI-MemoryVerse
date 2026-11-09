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
    <html lang="en" className="dark" suppressHydrationWarning>
      <head>
        <script
          dangerouslySetInnerHTML={{
            __html: `
              (function() {
                try {
                  var saved = localStorage.getItem('memoryverse_theme');
                  var theme = saved === 'light' ? 'light' : 'dark';
                  document.documentElement.classList.remove('dark', 'light');
                  document.documentElement.classList.add(theme);
                } catch(e) {}
              })();
            `,
          }}
        />
      </head>
      <body className="bg-[#F8F3F0] dark:bg-navy-950 text-[#282B4A] dark:text-[#F8F3F0] antialiased selection:bg-[#014BAA]/30 selection:text-white min-h-screen transition-colors">
        <Providers>{children}</Providers>
      </body>
    </html>
  );
}
