import type { Metadata, Viewport } from 'next';
import { GeistSans } from 'geist/font/sans';
import { GeistMono } from 'geist/font/mono';
import { Inter, JetBrains_Mono } from 'next/font/google';

import { auth } from '@/lib/nextauth';
import { CommandPalette } from '@/components/command-palette';
import { GlobalShortcuts } from '@/components/global-shortcuts';
import { Toaster } from '@/components/toaster';
import './globals.css';

// Phase 5 Linear V1 font pair. Source Serif 4 + Inter Tight have been
// retired — Linear V1 is Inter for chrome + body and JetBrains Mono for
// IDs, codes, timestamps, and keyboard hints. The variable names line up
// with `--font-sans` / `--font-mono` consumed by the @theme block in
// globals.css and the ported .qm-lin-* utility classes.
const sans = Inter({
  subsets: ['latin'],
  weight: ['400', '500', '600'],
  variable: '--font-sans',
  display: 'swap',
  fallback: ['-apple-system', 'BlinkMacSystemFont', 'Segoe UI', 'sans-serif'],
});
const mono = JetBrains_Mono({
  subsets: ['latin'],
  weight: ['400', '500'],
  variable: '--font-mono',
  display: 'swap',
  fallback: ['ui-monospace', 'SFMono-Regular', 'Menlo', 'monospace'],
});

export const metadata: Metadata = {
  title: {
    default: 'QuillMD',
    template: '%s · QuillMD',
  },
  description:
    'AI medical transcription for solo doctors. Send audio, get a signed note.',
  // app.quillmd.com is the authenticated surface. The marketing site
  // (quillmd.com) carries the public-facing content and should be
  // indexed; everything behind this layout sits behind session auth,
  // so block crawlers from following URLs they shouldn't fingerprint.
  robots: { index: false, follow: false },
};

export const viewport: Viewport = {
  themeColor: '#08090a',
  colorScheme: 'dark',
};

export default async function RootLayout({
  children,
}: {
  children: React.ReactNode;
}) {
  // Resolve auth once in the root layout so we can show/hide the authed
  // commands + shortcuts without each page having to wire them. auth()
  // is a cookie read and a DB lookup via the session callback — cheap
  // enough for every navigation.
  const session = await auth();
  const authed = Boolean(session?.user?.id);

  return (
    <html
      lang="en"
      data-theme="dark"
      className={`${GeistSans.variable} ${GeistMono.variable} ${sans.variable} ${mono.variable} dark`}
      suppressHydrationWarning
    >
      <body className="min-h-screen antialiased">
        {children}
        <CommandPalette authed={authed} />
        <GlobalShortcuts authed={authed} />
        <Toaster />
      </body>
    </html>
  );
}
