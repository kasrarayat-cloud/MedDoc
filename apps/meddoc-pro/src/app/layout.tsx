import type { Metadata } from "next";
import { Inter } from "next/font/google";
import "./globals.css";

const inter = Inter({
  variable: "--font-inter",
  subsets: ["latin"],
});

export const metadata: Metadata = {
  title: "MedDoc Pro - Medical Documentation, Automated",
  description:
    "Generate professional medical procedure notes in seconds. AI-powered documentation for LESI, CESI, PRP, LFB and more.",
  keywords: [
    "medical documentation",
    "procedure notes",
    "LESI",
    "CESI",
    "PRP",
    "pain management",
    "epidural",
    "automated",
  ],
  // pro.quillmd.com is the CRM/admin surface — everything behind this
  // layout sits behind session auth. The public-facing site is
  // quillmd.com; this one should not be indexed.
  robots: { index: false, follow: false },
};

export default function RootLayout({
  children,
}: Readonly<{
  children: React.ReactNode;
}>) {
  return (
    <html lang="en" className={`${inter.variable} h-full antialiased dark`}>
      <body
        className="min-h-full flex flex-col font-sans bg-slate-950 text-white"
        suppressHydrationWarning
      >
        {children}
      </body>
    </html>
  );
}
