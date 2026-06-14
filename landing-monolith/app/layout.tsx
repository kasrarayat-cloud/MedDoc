import type { Metadata, Viewport } from 'next';
import { Anton, Manrope, IBM_Plex_Mono } from 'next/font/google';
import './globals.css';

// Display: Anton — a single ultra-bold condensed weight; monolithic, cinematic.
const display = Anton({
  weight: '400',
  subsets: ['latin'],
  variable: '--font-display',
  display: 'swap',
});
// Body: Manrope — clean, geometric, characterful (not Inter/Roboto).
const body = Manrope({
  subsets: ['latin'],
  variable: '--font-body',
  display: 'swap',
});
// Terminal/data: IBM Plex Mono — authentic developer-terminal feel.
const mono = IBM_Plex_Mono({
  weight: ['400', '500', '600'],
  subsets: ['latin'],
  variable: '--font-mono',
  display: 'swap',
});

export const metadata: Metadata = {
  title: 'QuillMD — The note writes itself',
  description:
    'Evidence-anchored clinical notes from the visit conversation, machine-verified, with a review lane for anything it can’t ground. You sign every note. HIPAA-ready, BAA included, US-hosted.',
  robots: { index: false, follow: false }, // staging — keep it out of search
};

export const viewport: Viewport = {
  themeColor: '#06070a',
  width: 'device-width',
  initialScale: 1,
};

export default function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  return (
    <html lang="en" className={`${display.variable} ${body.variable} ${mono.variable}`}>
      <head>
        {/* Pre-paint: mark JS-capable so scroll-reveal sections start hidden
            ONLY when JS will animate them in. No-JS renders show everything. */}
        <script
          dangerouslySetInnerHTML={{ __html: "document.documentElement.classList.add('js')" }}
        />
      </head>
      <body>{children}</body>
    </html>
  );
}
