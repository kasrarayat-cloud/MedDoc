import type { Metadata, Viewport } from 'next';
import { Inter, JetBrains_Mono } from 'next/font/google';
import './globals.css';
import './landing.css';

// Phase 5 Linear V1 type pair. DM Sans + Source Serif 4 have been
// retired — Linear V1 is Inter for everything (chrome + body) plus
// JetBrains Mono for IDs / timestamps / keyboard hints. The variable
// names (`--font-sans` / `--font-mono`) line up with the @theme block in
// globals.css and the .qm-lin-* utility classes.
const sans = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600', '700'],
  variable: '--font-sans',
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

// Phase 5 Linear V1: pure dark canvas (#08090a) replaces the cream
// surface. Color scheme is dark, full-stop — there is no light mode.
export const viewport: Viewport = {
  themeColor: '#08090a',
  colorScheme: 'dark',
};

export default function RootLayout({ children }: { children: React.ReactNode }) {
  return (
    <html
      lang="en"
      className={`${sans.variable} ${mono.variable} dark`}
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">{children}</body>
    </html>
  );
}
