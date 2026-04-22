import type { Metadata, Viewport } from 'next';
import { Inter_Tight, JetBrains_Mono, Source_Serif_4 } from 'next/font/google';
import './globals.css';
import './landing.css';

const sans = Inter_Tight({
  subsets: ['latin'],
  weight: ['300', '400', '500', '600', '700', '800'],
  variable: '--font-sans',
  display: 'swap',
});

const serif = Source_Serif_4({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  style: ['normal', 'italic'],
  variable: '--font-serif',
  display: 'swap',
});

const mono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: {
    default: 'QuillMD — Stop writing notes. Start practicing medicine.',
    template: '%s · QuillMD',
  },
  description:
    'AI medical scribe for US doctors. Real-time SOAP notes, ICD-10/CPT codes, Rx drafts — $49/month flat.',
  openGraph: {
    title: 'QuillMD',
    description: 'Stop writing notes. Start practicing medicine.',
    type: 'website',
  },
};

export const viewport: Viewport = {
  themeColor: '#07060C',
  colorScheme: 'dark',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${serif.variable} ${mono.variable} dark`}
      data-theme="dark"
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
