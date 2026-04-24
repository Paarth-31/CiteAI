import type { Metadata } from "next";
import { Space_Grotesk, Space_Mono, DM_Sans } from "next/font/google";
import "./globals.css";
import VisualEditsMessenger from "../visual-edits/VisualEditsMessenger";
import ErrorReporter from "@/components/ErrorReporter";
import { Toaster } from "@/components/ui/sonner";
import Script from "next/script";

/* ─── Font Configuration ──────────────────────────────────────────── */

// Heading font — Space Grotesk (matches Hypefury-style bold tech headlines)
const spaceGrotesk = Space_Grotesk({
  subsets: ["latin"],
  variable: "--font-heading",
  weight: ["300", "400", "500", "600", "700"],
  display: "swap",
});

// Body font — DM Sans (clean, modern, highly legible)
const dmSans = DM_Sans({
  subsets: ["latin"],
  variable: "--font-sans",
  weight: ["300", "400", "500", "600"],
  style: ["normal", "italic"],
  display: "swap",
});

// Mono font — Space Mono (code snippets, badges, stats)
const spaceMono = Space_Mono({
  subsets: ["latin"],
  variable: "--font-mono",
  weight: ["400", "700"],
  display: "swap",
});

/* ─── Metadata ────────────────────────────────────────────────────── */

export const metadata: Metadata = {
  title: "Cite-AI | Document Analysis",
  description:
    "AI-powered document analysis, source mapping, and context validation framework",
  openGraph: {
    title: "Cite-AI | Document Analysis",
    description:
      "Upload documents, validate sources, and explore contextual relationships with AI.",
    type: "website",
  },
};

/* ─── Root Layout ─────────────────────────────────────────────────── */

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html
      lang="en"
      className={`dark ${spaceGrotesk.variable} ${dmSans.variable} ${spaceMono.variable}`}
    >
      <head>
        {/* Preconnect for Google Fonts (next/font handles the actual load) */}
        <link rel="preconnect" href="https://fonts.googleapis.com" />
        <link rel="preconnect" href="https://fonts.gstatic.com" crossOrigin="anonymous" />
      </head>
      <body
        className="
          bg-[#0f1117] text-[#f0f4f8]
          font-sans antialiased
          min-h-screen
          selection:bg-[#29b6f6] selection:text-[#050a0e]
        "
      >
        <ErrorReporter />
        <Script
          src="https://slelguoygbfzlpylpxfs.supabase.co/storage/v1/object/public/scripts//route-messenger.js"
          strategy="afterInteractive"
          data-target-origin="*"
          data-message-type="ROUTE_CHANGE"
          data-include-search-params="true"
          data-only-in-iframe="true"
          data-debug="false"
          data-custom-data='{"appName": "CiteAI", "version": "1.0.0", "greeting": "init"}'
        />
        {children}
        <Toaster />
        <VisualEditsMessenger />
      </body>
    </html>
  );
}
